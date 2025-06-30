import requests
import json
from typing import Optional, List, Union, Type, Dict, Any
from langchain.chat_models.base import BaseChatModel
from langchain.schema import AIMessage, HumanMessage, SystemMessage, BaseMessage, ChatGeneration, ChatResult
from pydantic import BaseModel

def schema_to_json_schema(schema: Union[Type[BaseModel], Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert a Pydantic BaseModel class or a JSON schema dict into a JSON schema dictionary.
    """
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        # Use Pydantic's JSON schema (Pydantic v2)
        return schema.model_json_schema()  # For Pydantic v1, use schema() instead
    elif isinstance(schema, dict):
        # Already a JSON schema dictionary
        return schema
    else:
        raise ValueError("Schema must be a Pydantic BaseModel subclass or a JSON schema dict.")

class ChatOllama(BaseChatModel):
    """LangChain-compatible chat model that interacts with a local Ollama LLM server."""
    # def __init__(self,
    #              model: str = None,
    #              base_url: str = None,
    #              temperature: float = 0.1,
    #             #  max_tokens: Optional[int] = None,
    #              top_p: Optional[float] = None,
    #              top_k: Optional[int] = None,
    #              stop: Optional[List[str]] = None,
    #              # Structured output parameters:
    #              ollama_output_schema: Union[Type[BaseModel], Dict[str, Any], None] = None,
    #              include_raw: bool = False):
    #     """
    #     Initialize the ChatOllama model.
    #     :param model: Name of the Ollama model to use (must be pulled to the local Ollama server).
    #     :param base_url: Base URL of the Ollama API (default "http://localhost:11434").
    #     :param temperature: Sampling temperature (0.0 to 1.0).
    #     :param max_tokens: Max number of tokens to generate (Ollama's num_predict).
    #     :param top_p: Top-p sampling parameter.
    #     :param top_k: Top-k sampling parameter.
    #     :param stop: Optional list of stop strings where generation will halt.
    #     :param ollama_output_schema: Optional Pydantic BaseModel class or JSON schema dict for structured output.
    #     :param include_raw: If True, include raw output along with parsed structured output.
    #     """
    #     self.model = model
    #     self.base_url = base_url
    #     self.temperature = temperature
    #     # self.max_tokens = max_tokens  # corresponds to Ollama's num_predict
    #     # self.top_p = top_p
    #     # self.top_k = top_k
    #     self.stop = stop
    #     # Structured output settings
    #     self.ollama_output_schema = ollama_output_schema
    #     self.include_raw = include_raw

    model: str
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    # max_tokens: Optional[int] = None
    # top_p: Optional[float] = None
    # top_k: Optional[int] = None
    stop: Optional[List[str]] = None
    ollama_output_schema: Union[Type[BaseModel], Dict[str, Any], None] = None
    include_raw: bool = False

    @property
    def _llm_type(self) -> str:
        """Unique identifier for this LLM type (for logging/tracing)."""
        return "ollama"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """
        Convert a list of LangChain BaseMessage objects to Ollama's message format.
        """
        ollama_msgs = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            else:
                # If there are other message types (like ToolMessage), map appropriately or raise
                role = "user"  # default to user for any unrecognized message type
            ollama_msgs.append({"role": role, "content": msg.content})
        return ollama_msgs

    def _generate(self,
                  messages: List[BaseMessage],
                  stop: Optional[List[str]] = None,
                  run_manager: Optional[Any] = None,
                  **kwargs: Any) -> ChatResult:
        """
        Generate a response from the local Ollama model for the given messages.
        Returns a LangChain ChatResult containing the AI's message.
        """
        # Prepare request payload for Ollama
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": False,
            "options": {"temperature": self.temperature}
        }
        # # Add generation parameters if specified
        # if self.max_tokens is not None:
        #     payload["num_predict"] = self.max_tokens
        # if self.top_p is not None:
        #     payload["top_p"] = self.top_p
        # if self.top_k is not None:
        #     payload["top_k"] = self.top_k
        # Handle stop tokens (combine stop from method args and instance, if any)
        final_stop = stop or self.stop
        if final_stop:
            payload["stop"] = final_stop

        # Include structured output format schema if provided
        if self.ollama_output_schema is not None:
            schema_json = schema_to_json_schema(self.ollama_output_schema)
            payload["format"] = schema_json

        # Send request to Ollama's chat API
        api_url = f"{self.base_url}/api/chat"
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        data = response.json()
        # Extract assistant content from response. Ollama's /api/chat returns a structure 
        # that includes the assistant message content.
        # We assume the response contains a field like data["message"]["content"].
        assistant_content = None
        if isinstance(data, dict):
            # If using OpenAI-compatible response (e.g., via /v1/chat/completions):
            if "choices" in data:
                # OpenAI format: take the first choice's message content
                assistant_content = data["choices"][0]["message"]["content"]
            elif "message" in data:
                # Ollama direct format: content is in data["message"]["content"]
                assistant_content = data["message"].get("content")
            else:
                # If the response itself is a JSON result matching the schema (when format is used),
                # then treat the entire response as the content (already structured).
                # Convert it to a string for consistent handling below.
                assistant_content = json.dumps(data)
        else:
            # If data is already a string (unlikely after .json()), handle accordingly
            assistant_content = str(data)

        if assistant_content is None:
            assistant_content = ""  # fallback to empty content if not found

        # Create an AIMessage for the assistant's reply
        ai_message = AIMessage(content=assistant_content)
        # Wrap in a ChatGeneration and ChatResult
        generation = ChatGeneration(message=ai_message)
        result = ChatResult(generations=[generation])
        return result

    def with_structured_output(self, schema: Union[Type[BaseModel], Dict[str, Any]], include_raw: bool = False):
        """
        Return a Runnable that, when invoked, will produce structured output according to the given schema.
        If include_raw is False, returns parsed output (Pydantic object or dict). 
        If include_raw is True, returns a dict with keys "raw", "parsed", and "parsing_error".
        """
        # We create a copy of this ChatOllama with schema configured, or use self if no change in base.
        base_llm = ChatOllama(model=self.model,
                              base_url=self.base_url,
                              temperature=self.temperature,
                            #   max_tokens=self.max_tokens,
                            #   top_p=self.top_p,
                            #   top_k=self.top_k,
                              stop=self.stop,
                              ollama_output_schema=schema,
                              include_raw=include_raw)
        # The returned object is a Runnable that uses base_llm to generate and then parses the output.
        # We can leverage the fact that BaseChatModel (and thus ChatOllama) itself is a Runnable, 
        # and implement parsing in a wrapper function.
        class StructuredOutputRunnable:
            def __init__(self, llm: ChatOllama, out_schema: Union[Type[BaseModel], Dict[str, Any]], raw: bool):
                self.llm = llm
                self.schema = out_schema
                self.include_raw = raw

            def invoke(self, prompt_input: Union[str, List[BaseMessage]]) -> Union[Dict[str, Any], BaseModel]:
                """
                Invoke the LLM on the given input (prompt or messages) and return structured output.
                """
                # Ensure input is in message format list
                if isinstance(prompt_input, str):
                    # Convert plain string to a single Human message
                    # prompt_msgs = [[HumanMessage(content=prompt_input)]]
                    prompt_msgs = [HumanMessage(content=prompt_input)]
                else:
                    prompt_msgs = prompt_input

                # Get the raw ChatResult from the LLM
                # chat_result: ChatResult = self.llm.generate(prompt_msgs)
                chat_result: ChatResult = self.llm._generate(prompt_msgs)
                # Extract the assistant's message content
                ai_msg: AIMessage = chat_result.generations[0].message
                raw_content = ai_msg.content

                # Try to parse the content as JSON
                parsed_output = None
                parsing_error = None
                try:
                    # If the schema is Pydantic, use model_validate to get an object
                    if isinstance(self.schema, type) and issubclass(self.schema, BaseModel):
                        # If content is a JSON string, ensure it's parsed to dict first
                        # If the content is already a JSON string from the model (it might include quotes if double-encoded),
                        # we attempt to load it.
                        data = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
                        parsed_output = self.schema.model_validate(data)  # Pydantic v2 parsing
                    elif isinstance(self.schema, dict):
                        # If a direct JSON schema dict was provided, just parse the JSON string to dict
                        parsed_output = json.loads(raw_content)
                    else:
                        raise ValueError("Unsupported schema type for structured output.")
                except Exception as e:
                    parsing_error = e

                if self.include_raw:
                    # Return a dictionary with raw message and parsed result (or error)
                    return {
                        "raw": ai_msg,
                        "parsed": parsed_output if parsing_error is None else None,
                        "parsing_error": parsing_error
                    }
                else:
                    # If parsing failed and raw output not requested, raise the error
                    if parsing_error:
                        raise parsing_error
                    # Return the parsed output directly (BaseModel instance or dict)
                    return parsed_output

        # Return an instance of the runnable wrapper
        return StructuredOutputRunnable(base_llm, schema, include_raw)
