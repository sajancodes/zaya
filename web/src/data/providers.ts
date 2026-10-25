export interface ProviderItem {
  id: string;
  name: string;
  category: 'CLOUD' | 'LOCAL' | 'HYBRID';
  capabilities: {
    tools: boolean;
    vision: boolean;
    streaming: boolean;
    liveVoice: boolean;
  };
  recommendedModel: string;
  endpointType: string;
  description: string;
  setupGuide: {
    steps: string[];
    link?: string;
    linkText?: string;
  };
}

export const PROVIDERS: ProviderItem[] = [
  {
    id: 'gemini',
    name: 'Google Gemini (Live & Standard)',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: true,
    },
    recommendedModel: 'models/gemini-3.8-live',
    endpointType: 'Native Google GenAI SDK / WebSockets',
    description: 'Primary low-latency voice path for Zaya. Powers conversational speech streaming (Nika voice), live multimodal desktop reasoning, and tool calling with zero intermediary lag.',
    setupGuide: {
      steps: [
        'Visit Google AI Studio (aistudio.google.com/app/apikey).',
        'Create a free API key under your Google Cloud project.',
        'Open Zaya First-Run Setup or right-click Zaya → Gemini API keys.',
        'Paste key (or multiple comma-separated keys for rate-limit failover).'
      ],
      link: 'https://aistudio.google.com/app/apikey',
      linkText: 'Open Google AI Studio ↗'
    }
  },
  {
    id: 'openai',
    name: 'OpenAI',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'gpt-4o',
    endpointType: 'OpenAI v1 REST / SSE',
    description: 'Cloud provider supporting complex coding supervisor sessions, deep technical reasoning, tool execution, and vision inspection.',
    setupGuide: {
      steps: [
        'Log in to platform.openai.com and generate an API key.',
        'In Zaya Settings → AI Engine → Provider, select OpenAI.',
        'Save key into the secure DPAPI vault.'
      ],
      link: 'https://platform.openai.com/api-keys',
      linkText: 'Open OpenAI Platform ↗'
    }
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'anthropic/claude-3.5-sonnet',
    endpointType: 'OpenAI-compatible unified API',
    description: 'Unified gateway providing instant access to Claude 3.5 Sonnet, DeepSeek V3, Llama 3.3, and hundreds of frontier models with one key.',
    setupGuide: {
      steps: [
        'Create an account at openrouter.ai and generate an API token.',
        'Select OpenRouter in Zaya AI Engine configuration.',
        'Choose your desired model routing ID.'
      ],
      link: 'https://openrouter.ai/keys',
      linkText: 'OpenRouter Console ↗'
    }
  },
  {
    id: 'groq',
    name: 'Groq',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'llama-3.3-70b-versatile',
    endpointType: 'Groq LPU Inference Engine',
    description: 'Ultra-fast LPU hardware delivering hundreds of tokens per second for near-instant desktop reasoning and rapid tool invocation.',
    setupGuide: {
      steps: [
        'Obtain a Groq API key from console.groq.com.',
        'Add key to Zaya provider settings.',
        'Ideal for fast coding checks and real-time response generation.'
      ],
      link: 'https://console.groq.com/keys',
      linkText: 'Groq Console ↗'
    }
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: false,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'deepseek-chat / deepseek-reasoner',
    endpointType: 'DeepSeek API',
    description: 'Exceptional open-weights reasoning and code generation models for deep coding passes and supervised mission planning.',
    setupGuide: {
      steps: [
        'Obtain your API key from platform.deepseek.com.',
        'Configure deepseek-reasoner for advanced architecture tasks in Zaya.'
      ],
      link: 'https://platform.deepseek.com',
      linkText: 'DeepSeek Platform ↗'
    }
  },
  {
    id: 'mistral',
    name: 'Mistral AI',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'mistral-large-latest / pixtral-large',
    endpointType: 'Mistral API',
    description: 'High-efficiency frontier models with multilingual capability, code reasoning, and vision understanding via Pixtral.',
    setupGuide: {
      steps: [
        'Generate an API key at console.mistral.ai.',
        'Configure in Zaya settings under Mistral provider.'
      ],
      link: 'https://console.mistral.ai',
      linkText: 'Mistral Console ↗'
    }
  },
  {
    id: 'xai',
    name: 'xAI (Grok)',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'grok-beta / grok-vision-beta',
    endpointType: 'xAI API',
    description: 'Frontier reasoning and visual comprehension with real-time world knowledge.',
    setupGuide: {
      steps: [
        'Access x.ai console and create an API key.',
        'Enter key in Zaya settings.'
      ]
    }
  },
  {
    id: 'together',
    name: 'Together AI',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
    endpointType: 'OpenAI-compatible REST',
    description: 'Fast cloud hosting for open models with function calling and JSON output support.',
    setupGuide: {
      steps: ['Register at api.together.xyz and copy your secret key into Zaya.']
    }
  },
  {
    id: 'cerebras',
    name: 'Cerebras',
    category: 'CLOUD',
    capabilities: {
      tools: true,
      vision: false,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'llama3.1-70b',
    endpointType: 'Cerebras Wafer-Scale Engine',
    description: 'Extremely high token-per-second throughput via Wafer-Scale cluster for near-zero latency reasoning.',
    setupGuide: {
      steps: ['Obtain a Cerebras Cloud key at cloud.cerebras.ai.']
    }
  },

  // LOCAL PROVIDERS
  {
    id: 'ollama',
    name: 'Ollama',
    category: 'LOCAL',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'qwen2.5:14b / llama3.2:3b',
    endpointType: 'http://localhost:11434/v1',
    description: 'Completely private local model execution. Zaya connects directly to your running Ollama server for zero-cloud token processing.',
    setupGuide: {
      steps: [
        'Install Ollama from ollama.com.',
        'Run `ollama run qwen2.5:14b` in your terminal.',
        'In Zaya AI Engine, select LOCAL PIPELINE → Ollama.',
        'No API keys required; 100% offline data retention.'
      ],
      link: 'https://ollama.com',
      linkText: 'Download Ollama ↗'
    }
  },
  {
    id: 'lm-studio',
    name: 'LM Studio',
    category: 'LOCAL',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'Qwen 2.5 7B / DeepSeek R1 GGUF',
    endpointType: 'http://localhost:1234/v1',
    description: 'Desktop GUI runner for GGUF models. Start local server with one click and let Zaya handle local actions securely.',
    setupGuide: {
      steps: [
        'Install LM Studio from lmstudio.ai.',
        'Download your desired GGUF model.',
        'Start the local inference server (port 1234).',
        'Zaya automatically connects to localhost:1234/v1.'
      ],
      link: 'https://lmstudio.ai',
      linkText: 'Download LM Studio ↗'
    }
  },
  {
    id: 'llama-cpp',
    name: 'llama.cpp Server',
    category: 'LOCAL',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'Quantized GGUF models',
    endpointType: 'http://localhost:8080/v1',
    description: 'C/C++ native inference engine for maximum CPU and GPU utilization with minimal memory overhead.',
    setupGuide: {
      steps: [
        'Run `llama-server.exe -m model.gguf --port 8080`.',
        'Point Zaya to http://localhost:8080 in local pipeline settings.'
      ]
    }
  },
  {
    id: 'vllm',
    name: 'vLLM',
    category: 'LOCAL',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'PagedAttention models',
    endpointType: 'http://localhost:8000/v1',
    description: 'High-throughput local/private server using PagedAttention for low-latency batch and streaming queries.',
    setupGuide: {
      steps: [
        'Start vLLM server: `vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000`.',
        'Configure Zaya AI Engine custom endpoint.'
      ]
    }
  },
  {
    id: 'custom-openai',
    name: 'Custom OpenAI-Compatible Provider',
    category: 'HYBRID',
    capabilities: {
      tools: true,
      vision: true,
      streaming: true,
      liveVoice: false,
    },
    recommendedModel: 'User defined',
    endpointType: 'Custom /v1/chat/completions',
    description: 'Connect Zaya to any private enterprise endpoint, cloud proxy, or experimental local server using standard OpenAI protocol.',
    setupGuide: {
      steps: [
        'Enter Base URL, model string, and optional auth token in Zaya Settings.',
        'Zaya validates streaming and function-calling schemas during test connection.'
      ]
    }
  }
];
