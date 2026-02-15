UBISOFT_REGISTRY = "SOFTWARE\\Ubisoft"
STEAM_REGISTRY = "Software\\Valve\\Steam"
UBISOFT_REGISTRY_LAUNCHER = "SOFTWARE\\Ubisoft\\Launcher"
UBISOFT_REGISTRY_LAUNCHER_INSTALLS = "SOFTWARE\\Ubisoft\\Launcher\\Installs"

UBISOFT_SETTINGS_YAML = "AppDataSomething/Ubisoft Game Launcher/settings.yml"

UBISOFT_CONFIGURATIONS_BLACKLISTED_NAMES = ["gamename", "l1", "l2", "thumbimage", "", "ubisoft game", "name"]

CHROME_USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/72.0.3626.121 Safari/537.36"
)

CLUB_GENOME_ID = "42d07c95-9914-4450-8b38-267c4e462b21"
CLUB_APPID = "82b650c0-6cb3-40c0-9f41-25a53b62b206"

LOGIN_URL = (
    f"https://connect.ubisoft.com/login?appId={CLUB_APPID}&genomeId={CLUB_GENOME_ID}"
    "&lang=en-US&nextUrl=https:%2F%2Fconnect.ubisoft.com%2Fready"
)
