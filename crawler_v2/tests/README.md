# Crawler v2 Test Notebooks

This directory contains Jupyter notebooks used for testing, debugging, and developing the HTML slicing pipeline functionality.

## Notebooks Overview

### `debug_slicing.ipynb`
- **Purpose**: Debug helpers for HTML slicing using Ollama
- **Key Features**:
  - Direct Ollama client calls with function calling
  - Tool schema building and response parsing
  - Focused HTML preprocessing with keyword extraction
  - Comprehensive logging and debugging output
  - Rule-based fallback slicing when LLM fails

### `fixed_slicing_pipeline.ipynb`
- **Purpose**: Fixed implementation avoiding ChatPromptTemplate issues
- **Key Features**:
  - Direct LLM invocation instead of ChatPromptTemplate
  - Schema injection into prompt to maintain structure
  - Robust JSON parsing with fallback handling
  - Conservative changes to existing codebase
  - Compatibility with existing Pydantic models

### `hypothesis_testing_empty_llm_outputs.ipynb`
- **Purpose**: Systematic testing for empty LLM response issues
- **Key Features**:
  - Tests multiple hypotheses for empty output problems
  - Model configuration testing (temperature, num_predict, etc.)
  - Prompt template variable conflict testing
  - Ollama connectivity and model availability testing
  - HTML content processing issue testing
  - Final working solution implementation

### `slicing_pipeline_final.ipynb`
- **Purpose**: Clean, working version using function calling with logging
- **Key Features**:
  - Uses Ollama function calling with `get_slices` tool
  - Passes exact Pydantic JSON schema to the tool
  - Comprehensive logging (HTML input, prompt, LLM output, final sliced HTML)
  - Always returns a `SliceSet` object
  - Handles both dict and object-style Ollama responses

### `slicing_pipeline_fixed_minimal.ipynb`
- **Purpose**: Minimal robust slicing pipeline
- **Key Features**:
  - Direct Ollama calls with selected model
  - Always returns `SliceSet` (never None) to avoid errors
  - Prints raw LLM output for debugging
  - Safe wrapper classes for response handling
  - Tool-based structured output support

## Usage Notes

- All notebooks are designed to work with the existing `prompts/generate_slices.md` prompt
- They use the same Pydantic models (`Slice` and `SliceSet`) for consistency
- Most notebooks include fallback mechanisms for when LLM calls fail
- The notebooks demonstrate different approaches to solving the HTML slicing problem

## Development History

These notebooks were created to solve issues with:
1. Empty LLM responses from gpt-oss:20b model
2. ChatPromptTemplate conflicts with HTML content
3. JSON parsing failures and tool calling issues
4. Inconsistent response formats from Ollama

The final working solutions can be found in `slicing_pipeline_final.ipynb` and `slicing_pipeline_fixed_minimal.ipynb`.
