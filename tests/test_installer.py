from unittest import TestCase
from lutris.installer import ScriptInterpreter, ScriptingError


class TestScriptInterpreter(TestCase):
    def test_script_with_correct_values_is_valid(self):
        script_data = """
        runner: foo
        installer: bar
        name: baz
        """
        interpreter = ScriptInterpreter(script_data)
        self.assertFalse(interpreter.errors)
        self.assertTrue(interpreter.is_valid())

    def test_move_requires_src_and_dst(self):
        interpreter = ScriptInterpreter("")
        with self.assertRaises(ScriptingError):
            interpreter._get_move_paths({})

    def test_get_command_returns_a_method(self):
        command, params = ScriptInterpreter._map_command({'move': 'whatever'})
        self.assertIn("bound method ScriptInterpreter.move", str(command))
        self.assertEqual(params, "whatever")

    def test_get_command_doesnt_return_private_methods(self):
        """ """
        with self.assertRaises(ScriptingError) as ex:
            command, params = ScriptInterpreter._map_command(
                {'_substitute': 'foo'}
            )
        self.assertEqual(ex.exception.message,
                         "The command substitute does not exists")
