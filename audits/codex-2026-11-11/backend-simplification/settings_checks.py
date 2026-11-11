"""Check explicit settings, serialization, spawn initialization and JSON overrides."""
import ast
import importlib
import json
import multiprocessing
from pathlib import Path
import pickle
import sys
import tempfile


def spawned_settings(module, settings, script, queue):
    driver = importlib.import_module(module)
    driver.configure(settings, script=script)
    queue.put(driver.current_settings())


def main():
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root / 'tools/GHOST'))
    from ghost_backend.runs.driver_settings import DriverSettings
    from ghost_backend.runs.config import configuration_payload, write_configuration, driver_contract
    from ghost_backend.runs.execution import driver_options, _driver_settings
    checks = []

    def check(name, condition):
        assert condition, name
        checks.append(name)
        print('PASS', name, flush=True)

    for name in ('runs.local_twod_driver', 'hpc.twod_driver', 'runs.local_bor_driver', 'hpc.bor_driver'):
        module = 'ghost_backend.' + name
        driver = importlib.import_module(module)
        driver.load_default_settings()
        settings = driver.current_settings()
        script = driver._SCRIPT
        check(name + ': configured keys are not injected into module globals',
              not set(settings).intersection(vars(driver)))
        check(name + ': legacy attribute reads resolve',
              all(getattr(driver, k) == v for k, v in settings.items()))
        check(name + ': snapshot pickle roundtrip',
              dict(pickle.loads(pickle.dumps(driver._SETTINGS))) == settings)
        changed = driver.current_settings()
        changed['FREQUENCIES_GHZ'].append(12345.)
        check(name + ': returned values do not mutate captured settings',
              driver.current_settings() == settings)
        provided = driver.current_settings()
        driver.configure(provided, script=script)
        provided['FREQUENCIES_GHZ'].append(12345.)
        check(name + ': input mutation does not mutate captured settings',
              driver.current_settings() == settings)
        missing = dict(settings)
        missing.pop('GEOMETRY_UNITS')
        try:
            driver.configure(missing, script=script)
        except ValueError as exc:
            check(name + ': missing parameter error preserved',
                  str(exc) == 'Driver script is missing parameter(s): GEOMETRY_UNITS')
        else:
            raise AssertionError('missing setting accepted')
        check(name + ': failed capture leaves prior snapshot intact', driver.current_settings() == settings)
        context = multiprocessing.get_context('spawn')
        queue = context.Queue()
        process = context.Process(target=spawned_settings, args=(module, settings, script, queue))
        process.start()
        received = queue.get(timeout=30)
        process.join(timeout=30)
        check(name + ': spawned worker restores identical settings', process.exitcode == 0 and received == settings)
        queue.close()
        if 'twod' in name:
            settings['FACTORIZATION'] = 'dense'
            settings['MESH_STRATEGY'] = 'global'
            driver.configure(settings, script=script)
            function = driver.submit if name.startswith('hpc') else driver.main
            check(name + ': execution decorator reads captured controls',
                  driver_options(_driver_settings(function.__wrapped__))['factorization'] == 'dense')
        else:
            with tempfile.TemporaryDirectory() as folder:
                parameter_script = Path(folder) / 'driver.py'
                parameter_script.write_text('from ' + module + ' import run\n')
                config = parameter_script.with_suffix('.config.json')
                write_configuration(config, configuration_payload('bor', {'N_MODES': 5}, driver._CONFIG_KEYS))
                driver.configure(settings, script=parameter_script, load_config_file=True)
                check(name + ': adjacent JSON override applied', driver.N_MODES == 5)
                check(name + ': JSON contract remains statically discoverable',
                      driver_contract(parameter_script) == ('bor', driver._CONFIG_KEYS))
                driver._ACTIVE_CONFIG_PATH.verify()
                check(name + ': JSON source fingerprint retained', driver._ACTIVE_CONFIG_PATH.path == config)
                before = driver.current_settings()
                invalid = dict(before, BOR_EXECUTION_OPTIONS={'factorization': 'invalid'})
                try:
                    driver.configure(invalid, script=parameter_script)
                except ValueError:
                    pass
                else:
                    raise AssertionError('invalid BoR options accepted')
                check(name + ': rejected BoR validation leaves previous settings intact',
                      driver.current_settings() == before)
    for p in (root / 'tools/GHOST/ghost_backend').rglob('*.py'):
        if '__pycache__' not in p.parts:
            ast.parse(p.read_text(), filename=str(p), feature_version=(3, 10))
    check('all GHOST Python files parse with 3.10 grammar', True)
    Path(__file__).with_name('settings-results.json').write_text(json.dumps(dict(passed=len(checks), checks=checks), indent=2)+'\n')


if __name__ == '__main__':
    main()
