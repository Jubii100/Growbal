import os
import sys
import asyncio
import django
from typing import List
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from anthropic._exceptions import OverloadedError
from langchain_core.prompts import ChatPromptTemplate
from asgiref.sync import sync_to_async
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, 'growbal_django')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growbal.settings")
django.setup()

from services.models import Service
from services.serializers import ServiceSerializer


@sync_to_async
def load_all_services():
    services = Service.objects.all()
    serializer = ServiceSerializer(services, many=True)
    return serializer.data


@sync_to_async
def update_service_general_descriptions(descriptions):
    services_to_update = Service.objects.filter(
        service_description=descriptions.company_service_description
    )
    services_to_update.update(
        general_service_description=descriptions.general_service_description
    )


class GeneralServiceDescription(BaseModel):
    company_service_description: str
    general_service_description: str


class GeneralServiceDescriptionOutput(BaseModel):
    general_service_description_output: List[GeneralServiceDescription]


def load_prompt(prompt_name):
    with open(f"prompts/{prompt_name}.md", "r") as f:
        return f.read()

async def main():
    prompt = load_prompt("generate_general_service_descriptions")

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", prompt),
        ("human", "Generate general service descriptions from the given company specific service descriptions")
    ])

    llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"], temperature=0
    ).with_structured_output(GeneralServiceDescriptionOutput)

    llm_chain = prompt_template | llm
    llm_chain = llm_chain.with_retry(
        retry_if_exception_type=(OverloadedError,),
        wait_exponential_jitter=True,
        stop_after_attempt=12
    )

    try:
        services = await load_all_services()
        company_service_descriptions = [
            service["service_description"]
            for service in services
            if service["service_description"]
        ]

        general_service_descriptions = None
        batch_size = 5

        for i in range(0, len(company_service_descriptions), batch_size):
            print(f"Processing batch {i//batch_size + 1} of {len(company_service_descriptions)//batch_size + 1}")
            try:
                response = llm_chain.invoke({"company_service_descriptions": company_service_descriptions[i:i+batch_size]})
                if general_service_descriptions is None:
                    general_service_descriptions = response
                else:
                    general_service_descriptions.general_service_description_output.extend(
                        response.general_service_description_output
                    )
            except Exception as e:
                print(f"Error processing batch {i//batch_size + 1}: {e}")

        for description in general_service_descriptions.general_service_description_output:
            try:
                await update_service_general_descriptions(description)
            except Exception as e:
                print(f"Error updating description '{description.company_service_description}': {e}")

        print("General service descriptions successfully added")

    except Exception as main_exception:
        print(f"Critical error encountered: {main_exception}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
