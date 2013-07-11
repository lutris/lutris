from tempfile import NamedTemporaryFile
from unittest import TestCase
from lutris.installer import ScriptInterpreter, ScriptingError


class MockInterpreter(ScriptInterpreter):
    """ a script interpreter mock """
    def _fetch_script(self, name):
        return {'runner': 'linux'}

    def is_valid(self):
        return True


class TestScriptInterpreter(TestCase):
    def test_script_with_correct_values_is_valid(self):
        script_data = """
        runner: foo
        installer: bar
        name: baz
        """
        with NamedTemporaryFile(delete=False) as temp_script:
            temp_script.write(script_data)
        interpreter = ScriptInterpreter(temp_script.name, None)
        self.assertFalse(interpreter.errors)
        self.assertTrue(interpreter.is_valid())

    def test_move_requires_src_and_dst(self):
        with NamedTemporaryFile(delete=False) as temp_script:
            temp_script.write("""
                            foo: bar
                            installer: {}
                            name: missing_runner
                            """)
        with self.assertRaises(ScriptingError):
            interpreter = ScriptInterpreter(temp_script.name, None)
            interpreter._get_move_paths({})

    def test_get_command_returns_a_method(self):
        interpreter = MockInterpreter('test', None)
        command, params = interpreter._map_command({'move': 'whatever'})
        self.assertIn("bound method MockInterpreter.move", str(command))
        self.assertEqual(params, "whatever")

    def test_get_command_doesnt_return_private_methods(self):
        """ """
        interpreter = MockInterpreter('test', None)
        with self.assertRaises(ScriptingError) as ex:
            command, params = interpreter._map_command(
                {'_substitute': 'foo'}
            )
        self.assertEqual(ex.exception.message,
                         "The command substitute does not exists")
