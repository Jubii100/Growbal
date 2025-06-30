import requests
import json
# from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from anthropic._exceptions import OverloadedError
import os
from pydantic import BaseModel
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
import os
from bs4 import BeautifulSoup
import re
from bs4 import BeautifulSoup
import re
from pydantic import Field
# from __future__ import print_function
# from IPython.display import display
from typing import Optional
from utils import Country, ProviderType
import anthropic
# import traceback

llm_model = os.environ["LLM_VERSION"]

# search_starters = ["Digital Marketing Firm", "Tax Consultancy Firm", "Cybersecurity Firm", "Legal Services Provider", "Healthcare Consultancy"]

# search_starters = ["Company formation service UAE", "Business formation service MENA", "Business registration services Gulf", "Business setup services Dubai", "Investment migration services UAE", "Second passport services", "Citizenship By investment", "economic passport services", "Golden Visa services", "Tax services UAE", "Tax Consultancy Firm Dubai", "Tax Calculation Services Dubai"]

class ResultRelevance(BaseModel):
    explanation: str = Field(description="Be extremely brief and concise with your explanation.")
    link: str

class RelevanceCheckOutput(BaseModel):
    most_relevant_result: Optional[ResultRelevance]

class SqlCommand(BaseModel):
    command: str


class ServiceProviderMemberDetails(BaseModel):
    name: str = Field(description="Very important. Find the name of the staff member from the CLEAN HTML content.")
    role_description: str = Field(description="Find the role description of the staff member from the CLEAN HTML content.")
    telephone: str = Field(description="Find the telephone number of the staff member from the CLEAN HTML content.")
    mobile: str = Field(description="Find the mobile number of the staff member from the CLEAN HTML content.")
    email: str = Field(description="Find the email address of the staff member from the CLEAN HTML content.")
    linkedin: Optional[str]
    facebook: Optional[str]
    instagram: Optional[str]
    twitter: Optional[str]
    additional_info: Optional[str]

class ServiceProviderOutput(BaseModel):
    service_title: Optional[str] = Field(description="Produce a suitable title for the service.")
    service_description: Optional[str] = Field(description="Do your due diligence on summarising the service description based on a holistic consideration of the scattered relevant service info throughout the entirety of the given CLEAN HTML content. Use a string, not a number. Null if unavailable.")
    rating_score: Optional[float] = Field(description="Must adhere to a rating standard out of 5. Must be a numeric rating score of type float. Use a number, not a string. Null if unavailable.")
    rating_description: Optional[str] = Field(description="Do your due diligence on summarising the rating description based on a holistic consideration of the scattered relevant rating info throughout the entirety of the given CLEAN HTML content. Use a string, not a number. Null if unavailable.")
    pricing: Optional[str]
    service_tags: List[str] = Field(description="Do your due diligence on summarising the service tags based on a holistic consideration of the scattered relevant service info throughout the entirety of the given CLEAN HTML content. Null if unavailable.")
    provider_type: ProviderType = Field("Company", description="ProviderType enum. Should be Company if the provider is a company or Agent if the provider is an agent.")
    # provider_type: ProviderType = Field(description="ProviderType enum. Should be Company if the provider is a company or Agent if the provider is an agent.")
    country: Optional[Country] = Field(description="Country enum.")
    name: Optional[str] = Field(description="Very important. Find the name of the company from the CLEAN HTML content.")
    vision: Optional[str] = Field(description="A brief summary of the company/firm's vision statement from the CLEAN HTML content.")
    logo: Optional[str] = Field(description="Mandatory. Find the absolute URL for the company logo from the CLEAN HTML content.")
    website: Optional[str] = Field(description="Very important. Must find the website link of the company from the HTML content or infer it from the base website link address. Null if unavailable.")
    linkedin: Optional[str] = Field(description="Null if unavailable.")
    facebook: Optional[str] = Field(description="Null if unavailable.")
    instagram: Optional[str] = Field(description="Null if unavailable.")
    telephones: List[str] = Field([], description="Mandatory. Must find at least one telephone number. Field must be a list of telephone numbers or empty list.")
    mobiles: List[str] = Field([], description="Mandatory. Must find at least one mobile number. Field must be a list of mobile numbers or empty list.")
    emails: List[str] = Field(
        [], description="Mandatory. Must find at least one email address of the company from the HTML content. Field must be a list of email addresses or empty list."
    )
    # emails: List[str] = Field(description="Very very important. Must find at least one email address of the company from the HTML content. Output must be a list of email addresses.")
    office_locations: Optional[str] = Field(description="Detailed address locations of the company offices eg. 123 Main St, City, Country, or description if address is not available. Null if unavailable.")
    key_individuals: Optional[str] = Field(description="Names and role descriptions of key people of the company. Null if unavailable.")
    representatives: Optional[str] = Field(description="Names and roles and contact details of representatives of the company. Null if unavailable.")
    # service_provider_member_details: Optional[List[ServiceProviderMemberDetails]]

class SearchTermOutput(BaseModel):
    search_term: str

class AboutUsOutput(BaseModel):
    about_us_link: Optional[List[str]]

def call_llm(model = "claude-3-5-sonnet-20241022", API_key = os.environ["ANTHROPIC_API_KEY"], prompt_template = None, input_dict = None, structured_output = None, temperature = 0):
    if prompt_template is None:
        raise ValueError("Prompt template is required")
    if input_dict is None:
        raise ValueError("Input dictionary is required")
    if structured_output is None:
        raise ValueError("Structured output is required")
    llm = ChatAnthropic(
        model=model,
        anthropic_api_key=API_key, temperature=temperature).with_structured_output(structured_output)
    llm_chain = prompt_template | llm
    llm_chain = llm_chain.with_retry(
        retry_if_exception_type=(OverloadedError,),
        wait_exponential_jitter=True,    
        stop_after_attempt=6
    )
    result = llm_chain.invoke(input_dict)
    return result

def search_serper(search_query):
    url = "https://google.serper.dev/search"
    
    payload = json.dumps({
        "q": search_query,
        "gl": "ae", 
        "num": 10,
        # "tbs": "qdr:w"
    })

    headers = {
        'X-API-KEY': os.environ["SERPER_API_KEY"],
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload, timeout=(3,4))
    results = json.loads(response.text)
    results_list = results['organic']

    all_results = []
    for id, result in enumerate(results_list, 1):
        result_dict = {
            'title': result['title'],
            'link': result['link'],
            'snippet': result['snippet'],
            'search_term': search_query,
            'id': id
        }
        all_results.append(result_dict)
    return all_results

def load_prompt(prompt_name):
    with open(f"prompts/{prompt_name}.md", "r") as f:
        return f.read()



def check_search_relevance(search_term: str, search_results: Dict[str, Any]) -> RelevanceCheckOutput:
    prompt = load_prompt("relevance_check_one_link")
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt),
        ("human", f"Check relevance of search results to the given search term (but most importantly make sure it is the actual company's official website, not a search facilitator website or other service of that sort): {search_term}")
    ])
    
    return call_llm(prompt_template = prompt_template, input_dict = {"search_term": search_term, 'search_results': search_results}, structured_output = RelevanceCheckOutput, temperature=0)


def convert_html_to_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Headers
    for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(h.name[1])
        h.replace_with('#' * level + ' ' + h.get_text() + '\n\n')
    
    # Links
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text()
        if href and text:
            a.replace_with(f'[{text}]({href})')
    
    # Bold
    for b in soup.find_all(['b', 'strong']):
        b.replace_with(f'**{b.get_text()}**')
    
    # Italic
    for i in soup.find_all(['i', 'em']):
        i.replace_with(f'*{i.get_text()}*')
    
    # Lists
    for ul in soup.find_all('ul'):
        for li in ul.find_all('li'):
            li.replace_with(f'- {li.get_text()}\n')
    
    for ol in soup.find_all('ol'):
        for i, li in enumerate(ol.find_all('li'), 1):
            li.replace_with(f'{i}. {li.get_text()}\n')
    
    # Get text and clean up
    text = soup.get_text()
    
    # Remove excess whitespace/newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.strip()
    
    return text

def scrape_and_save_markdown(relevant_results):
    markdown_contents = []
    for result in relevant_results:
        if 'link' in result:
            payload = {
                "api_key": os.environ["SCRAPING_API_KEY"], 
                "url": result['link'],
                "render_js": "true"
            }

            response = requests.get("https://scraping.narf.ai/api/v1/", params=payload)
            if response.status_code == 200:
                markdown_content = convert_html_to_markdown(response.content.decode())
                
                markdown_contents.append({
                    'url': result['link'],
                    'markdown': markdown_content,
                    'title': result.get('title', ''),
                    'id': result.get('id', '')
                })
            else:
                print(f"Failed to fetch {result['link']}: Status code {response.status_code}")

    print(f"Successfully downloaded and saved {len(markdown_contents)} pages as markdown")
    return markdown_contents




from scrapper import HtmlScraper
import tiktoken
import string
import secrets

import os
import django
import sys
from asgiref.sync import sync_to_async
from urllib.parse import urlparse
from django.core.validators import validate_email, URLValidator
from django.core.exceptions import ValidationError

sys.path.insert(0, 'growbal_django')

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growbal.settings")

django.setup()

from services.models import Service
from services.serializers import ServiceSerializer
from accounts.serializers import ServiceProviderProfileSerializer
from accounts.models import CustomUser, ServiceProviderProfile
from asgiref.sync import sync_to_async
# from django.db import transaction
from scraper.models import Scrape          # adjust import path as needed
from scraper.serializers import ScrapeSerializer
# from django.core.files import File

def validate_emails(email_list):
    valid_emails = []
    for email in email_list:
        try:
            validate_email(email)
            valid_emails.append(email)
        except ValidationError:
            error_message = f"Error validating email {email}"
            print(error_message)
            with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                log_file.write(error_message + "\n")
    return valid_emails


_url_validator = URLValidator()
def validate_url(raw_url: str | None) -> bool:
    if not raw_url:
        return False

    raw_url = raw_url.strip()
    if not urlparse(raw_url).scheme:
        raw_url = "http://" + raw_url

    try:
        _url_validator(raw_url)
        return True
    except ValidationError:
        return False


@sync_to_async
def get_or_create_user(name=None, email=None, username=None, password=None):
    user, created = CustomUser.objects.get_or_create_user(
        name=name,
        email=email,
        username=username,
        password=password
    )
    return user, created

@sync_to_async
def create_service(data):
    serializer = ServiceSerializer(data=data)
    if serializer.is_valid():
        service = serializer.save()
        return service
    else:
        error_message = f"Error validating service data {serializer.errors}"
        print(error_message)
        with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
            log_file.write(error_message + "\n")

@sync_to_async
def create_service_provider_profile(data):
    serializer = ServiceProviderProfileSerializer(data=data)
    if serializer.is_valid():
        profile = serializer.save()
        return profile
    else:
        error_message = f"Error validating service provider profile data {serializer.errors}"
        print(error_message)
        with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
            log_file.write(error_message + "\n")
        # raise ValueError(serializer.errors)

@sync_to_async
def create_scrape(data):
    serializer = ScrapeSerializer(data=data)
    if serializer.is_valid():
        scrape = serializer.save()
        return scrape
    else:
        error_message = f"Error validating scrape data {serializer.errors}"
        print(error_message)
        with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
            log_file.write(error_message + "\n")
        # raise ValueError(serializer.errors)

@sync_to_async
def check_similar_scrapes(base_url):
    return Scrape.check_similar_base_url(base_url=base_url)

def generate_password(length=8):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return password

# def count_tokens(text, model="gpt-4"):
#     encoding = tiktoken.encoding_for_model(model)
#     tokens = encoding.encode(text)
#     return len(tokens)

anthropic_client = anthropic.Anthropic()

def count_tokens(text, model="claude-3-5-sonnet-20241022", system_prompt=""):
    messages = [{"role": "user", "content": text}]
    
    response = anthropic_client.messages.count_tokens(
        model=model,
        system=system_prompt,
        messages=messages
    )

    return response.input_tokens

scraper = HtmlScraper(scraping_api_key=os.environ["SCRAPING_API_KEY"])

async def process_relevant_links(relevant_link, row_dict):
    if await check_similar_scrapes(relevant_link.link):
        return
    else:
        nav_html_list = []
        try:
                num_tokens_allowed = 38000
                max_page_tokens = 13000
                # min_page_num = 7
                i = 1
                clean_html_sum_links = []
                clean_html_sum = ""
                try:
                    nav_html_content_about = scraper.scrape_html_about(relevant_link.link)
                    if nav_html_content_about:
                        nav_html_list.append(nav_html_content_about)
                except Exception as e:
                    error_message = f"Error processing about page: {e}"
                    print(error_message)
                    with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                        log_file.write(error_message + "\n")

                try:
                    nav_html_content_contact = scraper.scrape_html_contact(relevant_link.link)
                    if nav_html_content_contact:
                        nav_html_list.append(nav_html_content_contact)
                except Exception as e:
                    error_message = f"Error processing contact page: {e}"
                    print(error_message)
                    with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                        log_file.write(error_message + "\n")

                try:
                    print("----------BASE PAGE----------")
                    print(relevant_link.link)
                    nav_html_content_base = scraper.scrape_html_base(relevant_link.link)
                    
                    clean_text, clean_html = scraper.clean_html_content(nav_html_content_base)
                    # scraper.save_html(clean_html, relevant_link.link)
                    if clean_html and (token_count := count_tokens(clean_html)) < max_page_tokens/2:
                        print(f"clean_html: {token_count} tokens")
                        print("approved")
                        clean_html_sum += f"CLEAN HTML PAGE {i}: ({relevant_link.link})\n\n"
                        clean_html_sum += clean_html + "\n\n"
                        clean_html_sum_links.append(relevant_link.link)
                    elif clean_text and (token_count := count_tokens(clean_text)) < max_page_tokens:
                        print(f"clean_text: {token_count} tokens")
                        print("approved")
                        clean_html_sum += f"ONLY TEXT FROM HTML PAGE {i}: ({relevant_link.link})\n\n"
                        clean_html_sum += clean_text + "\n\n"
                        clean_html_sum_links.append(relevant_link.link)
                    if nav_html_content_base:
                        nav_html_list.append(nav_html_content_base)
                except Exception as e:
                    error_message = f"Error processing base page: {e}"
                    print(error_message)
                    with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                        log_file.write(error_message + "\n")

                nav_links = []
                if len(nav_html_list) == 0 or not nav_html_list[0]: 
                    return
                for html_content in nav_html_list:
                    try:
                        nav_links.extend(scraper.get_nav_links(html_content))
                    except Exception as e:
                        error_message = f"Error processing nav links: {e}"
                        print(error_message)
                        with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                            log_file.write(error_message + "\n")
                print("----------NAV LINKS----------")
                print(nav_links)
                nav_links_str = "\n".join([f"{title}: {link}" for title, link, _ in nav_links])

                prompt = load_prompt("generate_about_us_link")
                prompt_template = ChatPromptTemplate.from_messages([
                    ("system", prompt),
                    ("human", f'Filter "about us" page, contact us page, services page, team page, or any similar page.')
                ])
                

                result = call_llm(prompt_template = prompt_template, input_dict = {"nav_links": nav_links_str, "base_url": relevant_link.link}, structured_output = AboutUsOutput, temperature=0)
                print(len(result.about_us_link))
                print(result.about_us_link)
                print("\n")
                for i, link in enumerate(result.about_us_link):
                    if link in clean_html_sum_links:
                        continue
                    if clean_html_sum and count_tokens(clean_html_sum) >= num_tokens_allowed:
                        continue
                    try:
                        html_content = scraper.scrape_html_base(link)
                        clean_text, clean_html = scraper.clean_html_content(html_content)
                        
                        if clean_html: print(f"count_tokens(clean_html) {i} before approval: {count_tokens(clean_html)}")
                        else: print(f"not clean_text {i} before approval: {clean_html}")

                        if clean_html and (count_tokens(clean_html) < max_page_tokens and count_tokens(clean_html) < num_tokens_allowed - count_tokens(clean_html_sum) if clean_html_sum else 0):
                            clean_html_sum += f"CLEAN HTML PAGE {i}: ({link})\n\n"
                            clean_html_sum += clean_html + "\n\n"
                            clean_html_sum_links.append(link)
                            print(f"{i} approved {link}")
                        elif (token_count := count_tokens(clean_html_sum)) < num_tokens_allowed:
                            print(token_count)
                            clean_html_sum += f"ONLY TEXT FROM HTML PAGE {i}: ({link})\n\n"
                            clean_html_sum += clean_text + "\n\n"
                            clean_html_sum_links.append(link)
                            print(f"{i} approved {link}")
                        else:
                            break
                        i += 1
                    except Exception as e:
                        error_message = f"Error processing {link}: {e}"
                        print(error_message)
                        with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                            log_file.write(error_message + "\n")
                
                # print("##########PROPRIETARY DATA RECORD OF THE ORGANIZATION##########\n")
                # print(str(row_dict))
                # with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                #     log_file.write("PROPRIETARY DATA RECORD OF THE ORGANIZATION\n\n" + str(row_dict) + "\n\n")
                # html_appendex = "PROPRIETARY DATA RECORD OF THE ORGANIZATION\n\n" + str(row_dict)
                clean_html_sum = clean_html_sum[:int((num_tokens_allowed*4)/2)]
                if clean_html_sum != "":
                    prompt = load_prompt("generate_fields_with_email")
                    prompt_template = ChatPromptTemplate.from_messages([
                        ("system", prompt),
                        ("human", f"Generate fields from the given HTML content.")
                    ])
                    
                    result = call_llm(prompt_template = prompt_template, input_dict = {"html_content": clean_html_sum, "proprietary_data": str(row_dict)}, structured_output = ServiceProviderOutput, temperature=0)
                    if result.emails == None:
                        print("result.email is Null")
                        result.emails = []
                    if result.telephones == None:
                        print("result.telephones is Null")
                        result.telephones = []
                    if result.mobiles == None:
                        print("result.mobiles is Null")
                        result.mobiles = []
                    if result.logo:
                        try:
                            result.logo = scraper.save_logo(result.logo)
                        except Exception as e:
                            error_message = f"Error saving logo: {e}"
                            print(error_message)
                            with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                                log_file.write(error_message + "\n")
                            result.logo = None

                result.emails = validate_emails(result.emails)
                if hasattr(result, 'name') and result.name and result.name != "":
                    if hasattr(result, 'name') and result.name and result.name != "":
                        user = None
                        if validate_url(result.website):
                            result.website = result.website.strip()
                            if not urlparse(result.website).scheme:
                                result.website = "http://" + result.website
                            try:
                                profile = await ServiceProviderProfile.objects.aget(website=result.website)
                                if profile:
                                    log_message = f"Profile already exists for this website: {result.website}"
                                    print(log_message)
                                    with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                                        log_file.write(log_message + "\n")
                                    user = profile.user
                            except Exception as e:
                                profile = None
                                error_message = f"Error getting profile from website: {e}"
                                print(error_message)
                                with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                                    log_file.write(error_message + "\n")
                        else:
                            result.website = None
                        
                        if not user and hasattr(result, 'emails') and result.emails and result.emails[0] != "":
                            print("creating user with name and email")
                            user_email = result.emails[0]
                            user_password = generate_password(8)
                            user, created = await get_or_create_user(name=result.name, email=user_email, username=user_email, password=user_password)
                            print("created user with email and name")
                        elif not user:
                            user_password = generate_password(8)
                            user, created = await get_or_create_user(name=result.name, password=user_password)
                            print("created user with name only")                        

                        if user:
                            # if not result.emails: result.emails = []
                            try:
                                profile = await ServiceProviderProfile.objects.aget(user_id=user.id)
                            except ServiceProviderProfile.DoesNotExist:
                                profile = None
                                error_message = f"Error profile does not exist!"
                                print(error_message)
                                with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                                    log_file.write(error_message + "\n")
                            except Exception as e:
                                profile = None
                                error_message = f"Error getting profile: {e}"
                                print(error_message)
                                with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                                    log_file.write(error_message + "\n")
                            
                            if not created and profile:
                                data = {
                                    "provider_type": result.provider_type[:50] if result.provider_type else profile.provider_type,
                                    "country": result.country[:100] if result.country else profile.country,
                                    "session_status": profile.session_status,
                                    "name": result.name[:255] if result.name else profile.name,
                                    "vision": result.vision or profile.vision,
                                    "website": result.website if validate_url(result.website) else profile.website,
                                    "logo": result.logo or profile.logo,
                                    "linkedin": result.linkedin if validate_url(result.linkedin) else profile.linkedin,
                                    "facebook": result.facebook if validate_url(result.facebook) else profile.facebook,
                                    "instagram": result.instagram if validate_url(result.instagram) else profile.instagram,
                                    "telephones": [x[:30] for x in result.telephones] if result.telephones else profile.telephones,
                                    "mobiles": [x[:30] for x in result.mobiles] if result.mobiles else profile.mobiles,
                                    "emails": result.emails if result.emails else profile.emails,
                                    "office_locations": result.office_locations or profile.office_locations,
                                    "key_individuals": result.key_individuals or profile.key_individuals,
                                    "representatives": result.representatives or profile.representatives
                                }
                                saved_profile, created_profile = await ServiceProviderProfile.objects.aupdate_or_create(
                                    user_id=user.id,             # lookup part – must stay unique
                                    defaults=data            # values to update/insert
                                )   
                                print(f"Profile updated: {saved_profile.name}")
                            else:
                                data = {
                                    "user": user.username,
                                    "provider_type": result.provider_type[:50] if result.provider_type else None,
                                    "country": result.country[:100] if result.country else None,
                                    "session_status": "inactive",
                                    "name": result.name[:255] if result.name else None,
                                    "vision": result.vision,
                                    "website": result.website if validate_url(result.website) else None,
                                    "logo": result.logo,
                                    "linkedin": result.linkedin if validate_url(result.linkedin) else None,
                                    "facebook": result.facebook if validate_url(result.facebook) else None,
                                    "instagram": result.instagram if validate_url(result.instagram) else None,
                                    "telephones": [x[:30] for x in result.telephones] if result.telephones else [],
                                    "mobiles": [x[:30] for x in result.mobiles] if result.mobiles else [],
                                    "emails": result.emails,
                                    "office_locations": result.office_locations,
                                    "key_individuals": result.key_individuals,
                                    "representatives": result.representatives
                                }
                                saved_profile = await create_service_provider_profile(data)
                                print(f"Profile created: {saved_profile.name}")

                            service_data_json = {
                                "profile": saved_profile.id,
                                "service_title": result.service_title[:255] if result.service_title else None,
                                "service_description": result.service_description,
                                "service_tags": result.service_tags,
                                "rating_score": result.rating_score,
                                "rating_description": result.rating_description,
                                "pricing": result.pricing
                            }
                            # Direct async call (works in Jupyter/IPython):
                            saved_service = await create_service(service_data_json)
                            print(f"Service created: {saved_service.service_title}")
                            scrape_data = {
                                "base_url": relevant_link.link,
                                "provider": saved_profile.id,
                                "service": saved_service.id,
                                "cleaned_html": clean_html_sum
                            }
                            saved_scrape = await create_scrape(scrape_data)
                            print(f"Scrape created: {saved_scrape.base_url}")
        except Exception as e:
            # raise ValueError(e)
            error_message = f"Error processing {relevant_link.link}: {e}"
            print(error_message)
            with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                log_file.write(error_message + "\n")
                # traceback.print_exc(file=log_file)

import argparse
import asyncio
from dotenv import load_dotenv
import pandas as pd

async def main(env_path: str) -> None:
    load_dotenv(env_path)
    print(f"Loaded envs from {env_path}")

    with open(os.environ["LOG_FILE_PATH"], "w") as log_file:
        log_file.write("")

    missed_df = pd.DataFrame()
    
    # Create or overwrite the missed entries file with an empty CSV
    missed_df_path = os.environ["MISSED_ENTRIES_PATH"]
    missed_df.to_csv(missed_df_path, index=False)
    
    df = pd.read_csv(os.environ["EMAIL_LIST_PATH"])
    df = df[['ORGANIZATION','INDUSTRY', 'WEBSITE', 'COUNTRY', 'CITY', 'FIRSTNAME', 'LASTNAME', 'EMAIL', 'LINKEDIN', 'DESIGNATION']]
    df['ORGANIZATION_COPY'] = df['ORGANIZATION']
    df = df.set_index('ORGANIZATION_COPY')
    df = df.dropna(axis=1, how='all')
    grouped = (
        df.groupby(df.index)
        .agg(lambda x: x.dropna().iloc[0] if x.notna().any() else None)
    )
    i = 1
    successful_entries = 0
    for organization, group in grouped.iterrows():
        log_message = f"Processing Entry {i}/{len(grouped)} Organization: {organization}"
        print(log_message)
        with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
            log_file.write(log_message + "\n")
        row_dict = group.to_dict()
        prompt = load_prompt("generate_a_search_term")
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", f"Generate only one suitable google search term to fetch the official website of the company/service provider/orginization: {row_dict['ORGANIZATION']}")
        ])

        result = call_llm(prompt_template = prompt_template, input_dict = {"row_dict": row_dict}, structured_output = SearchTermOutput, temperature=0)

        try:
            print(f"Processing search term: {result.search_term}")
            links = search_serper(result.search_term)
            # print(f"######### Found {len(links)} links ###########")
            # print(links)
            most_relevant_result = check_search_relevance(result.search_term, links).most_relevant_result
            if most_relevant_result:
                print(most_relevant_result)
                await process_relevant_links(most_relevant_result, row_dict)
                successful_entries += 1
                log_message = f"Successful processed entries {successful_entries}/{len(grouped)} Organization: {organization}"
                print(log_message)
                with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                    log_file.write(log_message + "\n")
            else:
                missed_df = pd.concat([missed_df, group.to_frame().T], ignore_index=True)
                missed_df_path = os.environ["MISSED_ENTRIES_PATH"]
                missed_df.to_csv(missed_df_path, index=False)
                log_message = f"No relevant link found for search term: {result.search_term}"
                print(log_message)
                with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                    log_file.write(log_message + "\n")
        except Exception as e:
            missed_df = pd.concat([missed_df, group.to_frame().T], ignore_index=True)
            missed_df_path = os.environ["MISSED_ENTRIES_PATH"]
            missed_df.to_csv(missed_df_path, index=False)
            error_message = f"Error processing Entry {i}/{len(grouped)} Organization: {organization}: {e}"
            print(error_message)
            with open(os.environ["LOG_FILE_PATH"], "a") as log_file:
                log_file.write(error_message + "\n")
        i += 1
        # if i == 10:
        #     break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the crawl with an .env file.")

    parser.add_argument(
        "env_path",
        help="Path to the .env file (e.g., envs/1.env)."
    )

    args = parser.parse_args()

    asyncio.run(main(args.env_path))