import time
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os

class CaptchaHandler:
    def __init__(self, driver, model):
        self.driver = driver
        self.model = model

    def save_screenshot(self, url, screenshot_path):
        self.driver.get(url)
        self.driver.save_screenshot(screenshot_path)

    def extract_and_solve_captcha(self, screenshot_path):
        img = Image.open(screenshot_path)
        response = self.model.generate_content([
            img,
            """Extract the captcha only. Response format:
            {        
                Contain Captcha : 'Yes/No',
                Captcha: (if yes)
            }"""
        ])
        captcha_json = json.loads(response.text.replace("```", "").replace("json", ""))
        return captcha_json

    def submit_captcha(self, captcha):
        captcha_input = self.driver.find_element(By.ID, 'captchacharacters')
        captcha_input.send_keys(captcha)
        time.sleep(2)
        submit_btn = self.driver.find_element(By.XPATH, '//button[contains(text(),"Continue shopping")]')
        submit_btn.click()
        time.sleep(5)

class ProductScraper:
    def __init__(self, driver):
        self.driver = driver
        self.products_df = pd.DataFrame([], columns=["prod_title", "prod_desc", "prod_price", "prod_ratings", "prod_img", "prod_link"])
        self.visited_links = {}

    def search_product(self, query):
        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.ID, "twotabsearchtextbox")))
        search_box = self.driver.find_element(By.ID, "twotabsearchtextbox")
        search_box.send_keys(query)
        self.driver.find_element(By.ID, "nav-search-submit-button").click()
        time.sleep(5)

    def extract_top_k_products_info(self, top_k=3):
        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.XPATH, "//div[@data-component-id]")))
        divs = self.driver.find_elements(By.XPATH, "//div[@data-component-id]")
        for div in divs:
            if len(self.visited_links) >= top_k:
                break
            find_anchor_tag_attempts = 0
            while(find_anchor_tag_attempts <3):
                try:
                    anchor_tags = div.find_elements(By.TAG_NAME, "a")
                    break
                except Exception as e:
                    find_anchor_tag_attempts += 1
                    print(f"Error finding anchor tag: {e}")
                    print("Trying again...")
            for a in anchor_tags:
                if len(self.visited_links) >= top_k:
                    break
                href = a.get_attribute('href')
                if self._is_valid_link(href):
                    self.visited_links[f"link_{len(self.visited_links) + 1}"] = href

                    click_on_link_attempts = 0
                    while(click_on_link_attempts<3):
                        try:
                            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(a))
                            a.click()
                            break
                        except Exception as e:
                            print(e)
                            click_on_link_attempts += 1

                    self.driver.switch_to.window(driver.window_handles[-1])  # Switch to the latest tab
                    print("Switched to new tab...")
                    self.scrape_product_details(href)

        

    def _is_valid_link(self, href):
        return (
            href not in self.visited_links.values()
            and "click?" not in href
            and "nb_sb_noss#" not in href
            and "https" in href
        )

    def scrape_product_details(self, href):
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "productTitle")))
            product_title = self.driver.find_element(By.ID, "productTitle").text
            product_price = self.driver.find_element(By.XPATH, '//*[@id="tp_price_block_total_price_ww"]//span[@class="a-price-whole"]').get_attribute("innerText").strip()+"INR"
            product_ratings = self.driver.find_element(By.ID, "acrPopover").get_attribute("title")
            product_details = self.driver.find_element(By.ID, "feature-bullets").text
            product_img = self.driver.find_element(By.ID, "landingImage").get_attribute("src")
            product_link = href

            self.products_df.loc[len(self.products_df)] = [
                product_title, product_details, product_price, product_ratings, product_img, product_link
            ]
        except Exception as e:
            print(f"Error scraping product details: {e}")
        finally:
            # Switch back to the original page (first window)
            self.driver.switch_to.window(driver.window_handles[0])
            print("Switched to the initial page...")

    def save_products(self, file_path):
        self.products_df.to_csv(file_path, index=False)

class WebAutomation:
    def __init__(self, driver, captcha_handler, product_scraper):
        self.driver = driver
        self.captcha_handler = captcha_handler
        self.product_scraper = product_scraper

    def run(self, query, url="https://www.amazon.in/", screenshot_path="./static/screenshot.png", output_file="./static/amazon_products_info.csv"):
        try:
            captcha_attempt_count =0
            while(captcha_attempt_count<3):
                try:
                    # Handle captcha
                    self.captcha_handler.save_screenshot(url, screenshot_path)
                    captcha_result = self.captcha_handler.extract_and_solve_captcha(screenshot_path)

                    if captcha_result.get("Contain Captcha") == "Yes":
                        captcha = captcha_result.get("Captcha")
                        self.captcha_handler.submit_captcha(captcha)
                        print("Cracked the captcha successfully...")
                    else:
                        print("No Captcha...")
                    break
                except Exception as e:
                    captcha_attempt_count += 1
                    print("Failed to solve Captcha...")
                    print("Trying again...")

            # Scrape products
            self.product_scraper.search_product(query)
            self.product_scraper.extract_top_k_products_info()
        except Exception as e:
            print(f"Error during web automation: {e}")
        finally:
            self.product_scraper.save_products(output_file)
            self.driver.quit()
        return self.product_scraper.products_df.to_json(orient = "records") if not self.product_scraper.products_df.empty else "It seems  either we are failed to fetch data or no data has been provided by Amazon(https://www.amazon.in/)."

### Initialize the WebDriver
service = Service(ChromeDriverManager().install())
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--headless")
driver = webdriver.Chrome(service=service, options= options)

### initiate the model
load_dotenv(".env", override= True)
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash-latest")  

captcha_handler = CaptchaHandler(driver, model)
product_scraper = ProductScraper(driver)
scrapper = WebAutomation(driver, captcha_handler, product_scraper)


if __name__ == "__main__":

    scrapper.run(query="latest dell laptops")
