UBISOFT_REGISTRY = "SOFTWARE\\Ubisoft"
STEAM_REGISTRY = "Software\\Valve\\Steam"
UBISOFT_REGISTRY_LAUNCHER = "SOFTWARE\\Ubisoft\\Launcher"
UBISOFT_REGISTRY_LAUNCHER_INSTALLS = "SOFTWARE\\Ubisoft\\Launcher\\Installs"

UBISOFT_SETTINGS_YAML = 'AppDataSomething/Ubisoft Game Launcher/settings.yml'

UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES = ["gamename", "l1", "l2", "thumbimage", '', 'ubisoft game', 'name']

CHROME_USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/72.0.3626.121 Safari/537.36"
)

CLUB_GENOME_ID = "85c31714-0941-4876-a18d-2c7e9dce8d40"
CLUB_APPID = "314d4fef-e568-454a-ae06-43e3bece12a6"

LOGIN_URL = (
    f"https://connect.ubisoft.com/login?appId={CLUB_APPID}&genomeId={CLUB_GENOME_ID}"
    "&lang=en-US&nextUrl=https:%2F%2Fconnect.ubisoft.com%2Fready"
)
