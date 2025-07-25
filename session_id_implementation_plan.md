# Session ID Implementation Plan

## Overview
This document outlines the required changes to pass `session_id` through the entire method call chain from the FastAPI chat interface down to the three core search functions: `search_profiles_by_service_tags`, `search_profiles_hybrid`, and `search_profiles`.

## Current Method Call Chain

```
FastAPI chat_wrapper (main_app_1.py:403)
    ↓
chat_response (chat_interface.py:468)
    ↓
enhanced_workflow_streaming (chat_interface.py:280)
    ↓
SearchAgent.search_streaming (search_agent.py:119)
    ↓
[One of three search functions in django_interface.py:]
    • search_profiles_by_service_tags (lines 90-173)
    • search_profiles_hybrid (lines 199-289)
    • search_profiles (lines 26-87)
        ↓
search_profiles_by_text (embedding_utils.py:156)
    ↓
find_similar_profiles (embedding_utils.py:114)
```

## Implementation Plan

### 1. FastAPI Chat Wrapper (`chat/main_app_1.py`)

**File**: `chat/main_app_1.py`  
**Function**: `chat_wrapper` (line 403)  
**Changes Required**:
- The `session_id` is already extracted on line 407-439
- Modify the call to `chat_response` on line 448 to pass `session_id`

**Before**:
```python
async for chunk in chat_response(message, history):
    yield chunk
```

**After**:
```python
async for chunk in chat_response(message, history, session_id):
    yield chunk
```

### 2. Chat Interface (`chat/chat_interface.py`)

**File**: `chat/chat_interface.py`  
**Function**: `chat_response` (line 468)  
**Changes Required**:
- Add `session_id` parameter to function signature
- Pass `session_id` to `enhanced_workflow_streaming`

**Before**:
```python
async def chat_response(message: str, history: List[List[str]]):
```

**After**:
```python
async def chat_response(message: str, history: List[List[str]], session_id: str):
```

**Function**: `enhanced_workflow_streaming` (line 280)  
**Changes Required**:
- Add `session_id` parameter to function signature
- Pass `session_id` to the SearchAgent

**Before**:
```python
async def enhanced_workflow_streaming(user_message: str):
```

**After**:
```python
async def enhanced_workflow_streaming(user_message: str, session_id: str):
```

- Locate the calls of enhanced_workflow_streaming function and add `session_id` parameter


- Modify the SearchAgent method calls "search_agent.search_streaming" and "search_agent.search" to include `session_id`
### 3. Search Agent (`growbal_intelligence/agents/search_agent.py`)

**File**: `growbal_intelligence/agents/search_agent.py`  
**Class**: `SearchAgent`  
**Method**: `search_streaming` (line 119)  
**Changes Required**:
- Add `session_id` parameter to method signature
- Pass `session_id` to all three search function calls

**Before**:
```python
async def search_streaming(self, search_input: SearchAgentInput):
```

**After**:
```python
async def search_streaming(self, search_input: SearchAgentInput, session_id: str):
```

- Do the same above procedures for the non-streaming/regular search methods chain, Namely "search" and "_search_non_streaming"


- Locate the calls to the three search functions and add `session_id` parameter to each
### 4. Django Interface (`growbal_intelligence/utils/django_interface.py`)

**File**: `growbal_intelligence/utils/django_interface.py`  

#### 4.1 `search_profiles_by_service_tags` (line 90)
**Changes Required**:
- Add `session_id` parameter to function signature
- The function can now use `session_id` for logging, session-based caching, or other session-specific operations

**Before**:
```python
def search_profiles_by_service_tags(tags: List[str], match_all: bool = False, max_results: int = 10):
```

**After**:
```python
def search_profiles_by_service_tags(tags: List[str], match_all: bool = False, max_results: int = 10, session_id: str = None):
```

#### 4.2 `search_profiles_hybrid` (line 199)
**Changes Required**:
- Add `session_id` parameter to function signature
- Pass `session_id` to internal call to `search_profiles` (line ~230)

**Before**:
```python
def search_profiles_hybrid(query: str, tags: List[str] = None, max_results: int = 10):
```

**After**:
```python
def search_profiles_hybrid(query: str, tags: List[str] = None, max_results: int = 10, session_id: str = None):
```

- Update the internal call to `search_profiles`:
**Before**:
```python
semantic_results = search_profiles(query, max_results=max_results)
```

**After**:
```python
semantic_results = search_profiles(query, max_results=max_results, session_id=session_id)
```

#### 4.3 `search_profiles` (line 26)
**Changes Required**:
- Add `session_id` parameter to function signature
- Pass `session_id` to `search_profiles_by_text` call

**Before**:
```python
def search_profiles(query: str, max_results: int = 10, minimum_similarity: float = 0.0):
```

**After**:
```python
def search_profiles(query: str, max_results: int = 10, minimum_similarity: float = 0.0, session_id: str = None):
```

- Update the call to `search_profiles_by_text`:
**Before**:
```python
results = search_profiles_by_text(query, max_results=max_results, minimum_similarity=minimum_similarity)
```

**After**:
```python
results = search_profiles_by_text(query, max_results=max_results, minimum_similarity=minimum_similarity, session_id=session_id)
```

### 5. Embedding Utils (`growbal_django/accounts/embedding_utils.py`)

**File**: `growbal_django/accounts/embedding_utils.py`  

#### 5.1 `search_profiles_by_text` (line 156)
**Changes Required**:
- Add `session_id` parameter to function signature
- Pass `session_id` to `find_similar_profiles` call

**Before**:
```python
def search_profiles_by_text(text: str, max_results: int = 10, minimum_similarity: float = 0.0):
```

**After**:
```python
def search_profiles_by_text(text: str, max_results: int = 10, minimum_similarity: float = 0.0, session_id: str = None):
```

- Update the call to `find_similar_profiles`:
**Before**:
```python
return find_similar_profiles(embedding, max_results=max_results, minimum_similarity=minimum_similarity)
```

**After**:
```python
return find_similar_profiles(embedding, max_results=max_results, minimum_similarity=minimum_similarity, session_id=session_id)
```

#### 5.2 `find_similar_profiles` (line 114)
**Changes Required**:
- Add `session_id` parameter to function signature
- This is the final function in the chain where `session_id` can be used for logging, caching, or database operations

**Before**:
```python
def find_similar_profiles(query_embedding: List[float], max_results: int = 10, minimum_similarity: float = 0.0):
```

**After**:
```python
def find_similar_profiles(query_embedding: List[float], max_results: int = 10, minimum_similarity: float = 0.0, session_id: str = None):
```

## Implementation Order

To implement these changes safely, follow this order:

1. **Bottom-up approach**: Start with the deepest functions first
2. **Order of implementation**:
   1. `find_similar_profiles` (embedding_utils.py)
   2. `search_profiles_by_text` (embedding_utils.py)
   3. `search_profiles`, `search_profiles_hybrid`, `search_profiles_by_service_tags` (django_interface.py)
   4. `SearchAgent.search_streaming` (search_agent.py)
   5. `enhanced_workflow_streaming` (chat_interface.py)
   6. `chat_response` (chat_interface.py)
   7. `chat_wrapper` (main_app_1.py)

## Testing Considerations

1. **Default parameter values**: All `session_id` parameters should be optional with default `None` to maintain backward compatibility
2. **Logging**: Add appropriate logging to track session_id flow through the system
3. **Error handling**: Ensure that missing or invalid session_id doesn't break the system
4. **Session validation**: Consider adding session validation at key points in the chain

## Benefits of This Implementation

1. **Session tracking**: Full traceability of user sessions through the entire search pipeline
2. **Caching**: Potential for session-based caching of search results
3. **Analytics**: Better user behavior analysis and session-based metrics
4. **Debugging**: Easier debugging of user-specific issues
5. **Personalization**: Foundation for session-based personalization features

## Files to Modify

1. `chat/main_app_1.py` - FastAPI chat wrapper
2. `chat/chat_interface.py` - Chat response functions  
3. `growbal_intelligence/agents/search_agent.py` - Search agent
4. `growbal_intelligence/utils/django_interface.py` - Three search functions
5. `growbal_django/accounts/embedding_utils.py` - Embedding utilities

## Additional Notes

- **Session ID Format**: The session_id is generated as a UUID4 string in `main_app_1.py:285`
- **Session Storage**: Session data is stored in `session_store` dictionary in `main_app_1.py:31`
- **Backwards Compatibility**: All changes maintain backward compatibility by making `session_id` optional
- **Future Enhancements**: This implementation provides foundation for session-based features like search history, personalized recommendations, and user analytics