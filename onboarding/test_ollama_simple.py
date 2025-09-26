#!/usr/bin/env python3
"""
Simple test script for Ollama GPT-OSS integration with LangChain compatibility
"""
import asyncio
from llm_wrapper import OnboardingLLM


async def test_basic_functionality():
    """Test basic LangChain-compatible functionality"""
    print("Testing LangChain-compatible Ollama integration...")
    
    try:
        # Initialize with Ollama model
        llm = OnboardingLLM(model_name="gpt-oss:20b")
        
        # Test search query generation (uses structured output)
        profile_text = """
        Company Name: Test Company UAE
        Country: UAE
        Services: Business consulting and advisory services
        Website: https://testcompany.ae
        """
        
        print("Testing search query generation...")
        queries = llm.generate_search_queries(profile_text, max_queries=2)
        
        if queries:
            print(f"Search queries generated successfully!")
            for i, query in enumerate(queries, 1):
                print(f"  {i}. {query.get('text', '')} (intent: {query.get('intent', '')})")
            return True
        else:
            print("No queries generated")
            return False
            
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run the test"""
    print("Starting Simple Ollama Integration Test")
    print("=" * 50)
    
    success = await test_basic_functionality()
    
    print("\n" + "=" * 50)
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
    
    if not success:
        print("\nMake sure:")
        print("  1. Ollama is running: ollama ps")
        print("  2. gpt-oss:20b model is loaded")
        print("  3. Model is accessible at localhost:11434")


if __name__ == "__main__":
    asyncio.run(main())
