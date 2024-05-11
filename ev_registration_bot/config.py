from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class TelegramSettings(BaseSettings):
    bot_token: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    bot_username: str = Field(..., validation_alias="TELEGRAM_BOT_USERNAME")


class Settings(BaseSettings):
    telegram: TelegramSettings = TelegramSettings()


# @lru_cache()
def get_settings() -> Settings:
    return Settings()
