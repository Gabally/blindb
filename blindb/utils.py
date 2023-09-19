import importlib, sys

class tColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    WHITE = '\033[0;97m'

def loadModule(path):
    spec = importlib.util.spec_from_file_location("sqli_adapter", path)
    foo = importlib.util.module_from_spec(spec)
    sys.modules["sqli_adapter"] = foo
    spec.loader.exec_module(foo)
    return foo

def printDoing(t):
    print(f"[{tColors.YELLOW}*{tColors.ENDC}]  {t}")

def printSuccess(t):
    print(f"\n\t[{tColors.GREEN}+{tColors.ENDC}] {t}\n")

def printError(t):
    print(f"[{tColors.RED}!{tColors.ENDC}] {t}\n")

def directOut(txt):
    sys.stdout.write(txt)
    sys.stdout.flush()