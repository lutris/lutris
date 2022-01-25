UBISOFT_REGISTRY = "SOFTWARE\\Ubisoft"
STEAM_REGISTRY = "Software\\Valve\\Steam"
UBISOFT_REGISTRY_LAUNCHER = "SOFTWARE\\Ubisoft\\Launcher"
UBISOFT_REGISTRY_LAUNCHER_INSTALLS = "SOFTWARE\\Ubisoft\\Launcher\\Installs"

UBISOFT_SETTINGS_YAML = 'AppDataSomething/Ubisoft Game Launcher/settings.yml'

UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES = ["gamename", "l1", '', 'ubisoft game', 'name']

CHROME_USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/72.0.3626.121 Safari/537.36"
)

CLUB_GENOME_ID = "fbd6791c-a6c6-4206-a75e-77234080b87b"
UBISOFT_APPID = "b8fde481-327d-4031-85ce-7c10a202a700"
CLUB_APPID = "314d4fef-e568-454a-ae06-43e3bece12a6"

LOGIN_URL = (
    f"https://connect.ubisoft.com/login?appId={UBISOFT_APPID}&genomeId={CLUB_GENOME_ID}"
    "&lang=en-US&nextUrl=https:%2F%2Fconnect.ubisoft.com%2Fready"
)
