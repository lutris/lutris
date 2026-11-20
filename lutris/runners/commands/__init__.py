import inspect
from typing import Any, Callable, TypeAlias

RegisteredRunnerTaskDict: TypeAlias = dict[str, Callable[..., Any]]
REGISTERED_TASK: RegisteredRunnerTaskDict = {}


def register_runner_task(func) -> Callable[..., Any]:
    def task_wrapper(*args, **kwargs) -> Any:
        return func(*args, **kwargs)

    func_name = ""
    module_name = ""
    for name, value in inspect.getmembers(func):
        # Locate the name member of the function
        # and register the task with the dictionary
        # The __module__ name is prepended for uniqueness
        if name == "__name__":
            func_name = value
        elif name == "__module__":
            module_name = value

        # Both the function name and method name has been found so break
        if func_name and module_name:
            break

    if func_name and module_name:
        REGISTERED_TASK[f"{module_name}.{func_name}"] = func
    return task_wrapper
