from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException
import discord
import aiohttp
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import os

logger = logging.getLogger("HabsenBot")

async def log_error_to_discord(error_message):
    LOG_WEBHOOK_URL = os.getenv("LOG_WEBHOOK_URL")
    if not LOG_WEBHOOK_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(LOG_WEBHOOK_URL, session=session)
            embed = discord.Embed(
                title="Kritik Hata",
                description=error_message[:2000],
                color=0xFF0000,
                timestamp=datetime.now(ZoneInfo("UTC"))
            )
            embed.set_footer(text="Habsen Bot")
            await webhook.send(embed=embed)
    except Exception as e:
        logger.error(f"Webhook gönderimi başarısız: {str(e)}")

async def check_username_validity(username):
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(f"https://habsen.com.tr/profile/{username}")
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        driver.find_element(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'hiç kullanıcı bulunamadı')]")
        return False
    except NoSuchElementException:
        return True
    except WebDriverException as e:
        logger.error(f"Selenium hatası (check_username_validity): {str(e)}")
        await log_error_to_discord(f"Selenium hatası (check_username_validity): {str(e)}")
        return False
    finally:
        if driver:
            driver.quit()

async def check_motto(username, code):
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(f"https://habsen.com.tr/profile/{username}")
        motto_element = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "KOD-")]'))
        )
        motto_text = motto_element.text.strip().replace('\u00A0', '').lower()
        return code.lower() in motto_text
    except WebDriverException as e:
        logger.error(f"Selenium hatası (check_motto): {str(e)}")
        await log_error_to_discord(f"Selenium hatası (check_motto): {str(e)}")
        return False
    finally:
        if driver:
            driver.quit()
