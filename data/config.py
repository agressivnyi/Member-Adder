from environs import Env

env = Env()
env.read_env()

dev = env.str("DEV")

BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS")
DB_NAME = env.str("DB_NAME")
HELP_URL = env.str("HELP_URL")
ADMIN_LINK = env.str("ADMIN_LINK")

API_ID = env.int("API_ID")
API_HASH = env.str("API_HASH")

base_type = env.str("DB_TYPE")
base_host = env.str("DB_HOST")
base_port = env.str("DB_PORT")
base_user = env.str("DB_USER")
base_pass = env.str("DB_PASS")
base_name = env.str("DB_NAME")
base_settings = (
    f"{base_type}://{base_user}:{base_pass}@{base_host}:{base_port}/{base_name}"
    if all((base_type, base_user, base_pass, base_host, base_name, base_port))
    else f"sqlite+aiosqlite:///{base_name}.db"
)
base_settings_for_create = (
    f"{base_type}://{base_user}:{base_pass}@{base_host}:{base_port}/{base_name}"
    if all((base_type, base_user, base_pass, base_host, base_name, base_port))
    else f"sqlite:///{base_name}.db"
)
system_version = env.str("SYSTEM_VERSION")
app_version = env.str("APP_VERSION")
