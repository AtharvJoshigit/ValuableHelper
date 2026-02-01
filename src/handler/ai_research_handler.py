"""
AI Research Handler
Handles different types of research queries using configured AI models
"""
from typing import Dict, List, Optional, Union, Literal
from datetime import datetime
from client.universal_ai_client import UniversalAIClient, OutputFormat
from handler.config import get_config
from prompts import research_propmts as rp
import json


class ResearchOutput:
    """Container for research outputs (text, images, or both)."""
    
    def __init__(
        self,
        text: Optional[str] = None,
        images: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Initialize research output.
        
        Args:
            text: Text content
            images: List of image URLs or paths
            metadata: Additional metadata
        """
        self.text = text
        self.images = images or []
        self.metadata = metadata or {}
    
    def has_text(self) -> bool:
        """Check if output has text."""
        return self.text is not None and len(self.text) > 0
    
    def has_images(self) -> bool:
        """Check if output has images."""
        return len(self.images) > 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "images": self.images,
            "metadata": self.metadata
        }
    
    def __str__(self) -> str:
        """String representation."""
        parts = []
        if self.has_text():
            parts.append(f"Text ({len(self.text)} chars)")
        if self.has_images():
            parts.append(f"Images ({len(self.images)})")
        return f"ResearchOutput({', '.join(parts)})"


class AIResearchHandler:
    """
    AI Research Handler for different types of research queries.
    Uses configured providers and models from AIConfig.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the research handler.
        
        Args:
            config_file: Path to config file (optional)
        """
        self.config = get_config()
        if config_file:
            self.config.config_file = config_file
            self.config.config = self.config._load_config()
        
        print("✓ AI Research Handler initialized")
    
    def _create_client(self, method: str) -> UniversalAIClient:
        """
        Create AI client based on method configuration.
        
        Args:
            method: Method name (handle_research, handle_research_on_trend, todays_research)
            
        Returns:
            Configured UniversalAIClient instance
        """
        provider = self.config.get_provider(method)
        model = self.config.get_model(method)
        
        return UniversalAIClient(provider=provider, model=model)
    
    def _generate_image(self, prompt: str) -> List[str]:
        """
        Generate image using configured image generation model.
        
        Args:
            prompt: Image generation prompt
            
        Returns:
            List of image URLs
        """
        try:
            # For now, using OpenAI DALL-E (you can make this configurable too)
            from openai import OpenAI
            import os
            
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            image_config = self.config.get("image_generation")
            
            response = client.images.generate(
                model=image_config.get("model", "dall-e-3"),
                prompt=prompt,
                size=image_config.get("size", "1024x1024"),
                quality=image_config.get("quality", "standard"),
                n=1
            )
            
            return [response.data[0].url]
        
        except Exception as e:
            print(f"⚠️  Error generating image: {e}")
            return []
    
    def handle_research(
        self,
        topic: str,
        include_images: bool = False,
        output_format: Literal["text", "json"] = "text"
    ) -> ResearchOutput:
        """
        Handle general research on a topic.
        
        Args:
            topic: Research topic
            include_images: Whether to generate related images
            output_format: Output format (text or json)
            
        Returns:
            ResearchOutput containing text and/or images
        """
        print(f"\n🔍 Researching: {topic}")
        
        # Create client for this method
        client = self._create_client("handle_research")
        
        # Get configuration
        config = self.config.get("handle_research")
        
        # Build research prompt
        # system_prompt = """You are a research assistant. Provide comprehensive, 
        # well-structured research on the given topic. Include key facts, current trends, 
        # and relevant insights. Be informative and accurate."""
        
        prompt = f"""Research the following topic and provide a detailed report:

Topic: {topic}

Provide a well-structured, informative research report."""
        
        # Determine output format
        fmt = OutputFormat.JSON_OBJECT if output_format == "json" else OutputFormat.TEXT
        
        # Get research results
        text_result = client.chat(
            message=prompt,
            system_prompt=rp.research_topic_system_prompt,
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 2000),
            output_format=fmt
        )
        
        # Handle JSON output
        if output_format == "json" and isinstance(text_result, dict):
            text_result = json.dumps(text_result, indent=2)
        
        # Generate images if requested
        images = []
        if include_images:
            print("🎨 Generating related image...")
            image_prompt = f"A professional, informative illustration representing: {topic}"
            images = self._generate_image(image_prompt)
        
        # Create output
        output = ResearchOutput(
            text=text_result,
            images=images,
            metadata={
                "topic": topic,
                "method": "handle_research",
                "provider": config.get("provider"),
                "model": config.get("model"),
                "timestamp": datetime.now().isoformat(),
                "output_format": output_format
            }
        )
        
        print(f"✓ Research completed: {output}")
        return output
    
    def handle_research_on_trend(
        self,
        topic: str,
        include_images: bool = False,
        output_format: Literal["text", "json"] = "text"
    ) -> ResearchOutput:
        """
        Handle research focused on current trends.
        
        Args:
            topic: Trend topic to research
            include_images: Whether to generate related images
            output_format: Output format (text or json)
            
        Returns:
            ResearchOutput containing text and/or images
        """
        print(f"\n📈 Researching trends: {topic}")
        
        # Create client for this method
        client = self._create_client("handle_research_on_trend")
        
        # Get configuration
        config = self.config.get("handle_research_on_trend")
        
        # Build trend research prompt
        system_prompt = """You are a trend analyst. Provide insights on current and 
        emerging trends related to the given topic. Focus on what's happening now, 
        predictions, and implications. Be data-driven and forward-looking."""
        
        prompt = f"""Analyze current trends related to:

Topic: {topic}

Please provide:
1. Current trending developments
2. Recent news and updates
3. Emerging patterns and shifts
4. Market/industry impact
5. Future predictions and implications
6. Key statistics or data points (if available)

Focus on what's trending NOW and where things are headed."""
        
        # Determine output format
        fmt = OutputFormat.JSON_OBJECT if output_format == "json" else OutputFormat.TEXT
        
        # Get trend analysis
        text_result = client.chat(
            message=prompt,
            system_prompt=system_prompt,
            temperature=config.get("temperature", 0.8),
            max_tokens=config.get("max_tokens", 3000),
            output_format=fmt
        )
        
        # Handle JSON output
        if output_format == "json" and isinstance(text_result, dict):
            text_result = json.dumps(text_result, indent=2)
        
        # Generate images if requested
        images = []
        if include_images:
            print("🎨 Generating trend visualization...")
            image_prompt = f"A modern, dynamic visualization showing trending aspects of: {topic}"
            images = self._generate_image(image_prompt)
        
        # Create output
        output = ResearchOutput(
            text=text_result,
            images=images,
            metadata={
                "topic": topic,
                "method": "handle_research_on_trend",
                "provider": config.get("provider"),
                "model": config.get("model"),
                "timestamp": datetime.now().isoformat(),
                "output_format": output_format
            }
        )
        
        print(f"✓ Trend research completed: {output}")
        return output
    
    def todays_research(
        self,
        include_images: bool = False,
        output_format: Literal["text", "json"] = "text",
        categories: Optional[List[str]] = None
    ) -> ResearchOutput:
        """
        Generate today's research digest covering multiple topics.
        
        Args:
            include_images: Whether to generate related images
            output_format: Output format (text or json)
            categories: Specific categories to focus on (optional)
            
        Returns:
            ResearchOutput containing text and/or images
        """
        print(f"\n📰 Generating today's research digest...")
        
        # Create client for this method
        client = self._create_client("todays_research")
        
        # Get configuration
        config = self.config.get("todays_research")
        
        # Default categories
        if not categories:
            categories = [
                "Technology",
                "Science",
                "Business",
                "Health",
                "Environment"
            ]
        
        # Build today's research prompt
        today = datetime.now().strftime("%B %d, %Y")
        
        system_prompt = """You are a daily research digest creator. Provide a 
        comprehensive overview of important topics and developments. Be informative, 
        engaging, and cover diverse areas. Focus on what's relevant and interesting."""
        
        prompt = f"""Create a research digest for today ({today}).

Cover these categories:
{chr(10).join(f"- {cat}" for cat in categories)}

For each category, provide:
1. Key topic or development
2. Brief explanation (2-3 sentences)
3. Why it matters

Make it informative, engaging, and easy to read.
Aim for a balanced overview across all categories."""
        
        # Determine output format
        fmt = OutputFormat.JSON_OBJECT if output_format == "json" else OutputFormat.TEXT
        
        # Get today's research
        text_result = client.chat(
            message=prompt,
            system_prompt=system_prompt,
            temperature=config.get("temperature", 0.9),
            max_tokens=config.get("max_tokens", 4000),
            output_format=fmt
        )
        
        # Handle JSON output
        if output_format == "json" and isinstance(text_result, dict):
            text_result = json.dumps(text_result, indent=2)
        
        # Generate images if requested
        images = []
        if include_images:
            print("🎨 Generating digest illustration...")
            image_prompt = f"A professional daily digest cover image for {today}, showing technology and innovation"
            images = self._generate_image(image_prompt)
        
        # Create output
        output = ResearchOutput(
            text=text_result,
            images=images,
            metadata={
                "method": "todays_research",
                "date": today,
                "categories": categories,
                "provider": config.get("provider"),
                "model": config.get("model"),
                "timestamp": datetime.now().isoformat(),
                "output_format": output_format
            }
        )
        
        print(f"✓ Today's research completed: {output}")
        return output
    
    def save_output(self, output: ResearchOutput, filepath: str):
        """
        Save research output to file.
        
        Args:
            output: ResearchOutput to save
            filepath: Path to save file
        """
        with open(filepath, 'w') as f:
            json.dump(output.to_dict(), f, indent=2)
        print(f"✓ Output saved to: {filepath}")
    
    def print_output(self, output: ResearchOutput):
        """
        Print research output in a formatted way.
        
        Args:
            output: ResearchOutput to print
        """
        print("\n" + "=" * 70)
        print("RESEARCH OUTPUT")
        print("=" * 70)
        
        if output.has_text():
            print("\n📄 TEXT CONTENT:")
            print("-" * 70)
            print(output.text)
        
        if output.has_images():
            print("\n🖼️  IMAGES:")
            print("-" * 70)
            for i, img_url in enumerate(output.images, 1):
                print(f"{i}. {img_url}")
        
        print("\n📊 METADATA:")
        print("-" * 70)
        for key, value in output.metadata.items():
            print(f"{key}: {value}")
        
        print("\n" + "=" * 70)


# Example usage
# if __name__ == "__main__":
    # print("=" * 70)
    # print("AI Research Handler - Demo")
    # print("=" * 70)
    
    # # Create handler
    # handler = AIResearchHandler()
    
    # # Example 1: General research
    # print("\n" + "=" * 70)
    # print("EXAMPLE 1: General Research")
    # print("=" * 70)
    
    # output = handler.handle_research(
    #     topic="Artificial Intelligence in Healthcare",
    #     include_images=False
    # )
    # handler.print_output(output)
    
    # # Example 2: Trend research
    # print("\n" + "=" * 70)
    # print("EXAMPLE 2: Trend Research")
    # print("=" * 70)
    
    # output = handler.handle_research_on_trend(
    #     topic="Electric Vehicles",
    #     include_images=False
    # )
    # handler.print_output(output)
    
    # # Example 3: Today's research
    # print("\n" + "=" * 70)
    # print("EXAMPLE 3: Today's Research Digest")
    # print("=" * 70)
    
    # output = handler.todays_research(
    #     include_images=False,
    #     categories=["AI", "Space", "Climate"]
    # )
    # handler.print_output(output)
    
    # # Example 4: With custom config
    # print("\n" + "=" * 70)
    # print("EXAMPLE 4: Custom Configuration")
    # print("=" * 70)
    
    # # Change config for a specific method
    # handler.config.set(
    #     "handle_research",
    #     provider="groq",
    #     model="llama-3.3-70b-versatile",
    #     temperature=0.5
    # )
    
    # output = handler.handle_research(
    #     topic="Quantum Computing",
    #     include_images=False
    # )
    # print(f"\nUsed provider: {output.metadata['provider']}")
    # print(f"Used model: {output.metadata['model']}")