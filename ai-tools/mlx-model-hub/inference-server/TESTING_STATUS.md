# Unified MLX App - Testing Status

**Date:** 2026-01-11
**Tested By:** Claude Sonnet 4.5

## Environment
- **OS:** macOS (Darwin 25.2.0)
- **Python:** 3.12
- **Package Manager:** uv
- **Branch:** feature/initial-setup

## Testing Summary

### ✅ Working Features

1. **Text Chat / LLM** - FULLY FUNCTIONAL
   - Model: `mlx-community/Qwen2.5-7B-Instruct-4bit`
   - API Endpoint: `/v1/chat/completions`
   - Tested successfully with streaming and non-streaming responses
   - Response caching works correctly

2. **Web UI** - FUNCTIONAL
   - Gradio 6.x compatibility issues resolved
   - UI loads without errors at http://localhost:7860
   - API accessible at http://localhost:8080

3. **API Server** - FUNCTIONAL
   - FastAPI backend running correctly
   - OpenAI-compatible API endpoints
   - Health check endpoint working

### ⚠️ Partially Working / Issues Found

4. **Text-to-Speech (TTS)** - NOT FUNCTIONAL
   - **Issue:** Kokoro TTS model has undocumented dependencies
   - **Missing Dependencies:**
     - ✅ loguru (added)
     - ✅ misaki (added)
     - ✅ num2words (added)
     - ❌ spacy (NOT added - large package ~500MB with language models)
   - **Status:** Model fails to load due to missing spacy
   - **Fix Required:** Add `spacy` and download language models
   ```bash
   uv add spacy
   uv run python -m spacy download en_core_web_sm
   ```

5. **Vision / VLM** - NOT TESTED VIA API
   - Model: `mlx-community/Qwen2-VL-2B-Instruct-4bit`
   - Vision model loads successfully when tested standalone
   - API endpoint `/v1/chat/completions` does not support vision (multimodal messages)
   - Vision features only available through Gradio UI, not API
   - Requires UI testing to verify functionality

6. **Speech-to-Text (STT)** - NOT TESTED
   - Model: `mlx-community/whisper-large-v3-turbo`
   - API Endpoint: `/v1/audio/transcriptions`
   - No test audio file available
   - Requires manual testing with actual audio input

7. **Image Generation** - NOT IMPLEMENTED
   - Placeholder functionality in UI
   - No actual model or generation code present

## Fixed Issues

### 1. Gradio 6.x Compatibility (FIXED ✅)
- **Problem:** App failed to start due to deprecated Gradio parameters
- **Changes Made:**
  - Removed `show_copy_button` from Chatbot and Textbox components
  - Removed `type="messages"` from Chatbot components
  - Moved `theme` and `css` from Blocks constructor to launch() method
- **Commit:** `4c25038`

### 2. TTS Dependencies (PARTIALLY FIXED ⚠️)
- **Problem:** Kokoro model import failed due to missing dependencies
- **Dependencies Added:** loguru, misaki, num2words
- **Still Missing:** spacy (large dependency, requires explicit installation)
- **Commit:** `454a709`

## Recommendations

1. **High Priority:**
   - Add spacy dependency for TTS functionality
   - Test Vision features through UI
   - Create test audio file and verify STT

2. **Medium Priority:**
   - Implement vision support in API (multimodal messages)
   - Add better error messages for missing dependencies
   - Document dependency installation in README

3. **Low Priority:**
   - Implement image generation feature or remove placeholder
   - Add integration tests for all features
   - Set up CI/CD pipeline

## How to Test Manually

### Chat
```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen2.5-7B-Instruct-4bit","messages":[{"role":"user","content":"Hello"}]}'
```

### TTS (after fixing spacy)
```bash
curl http://localhost:8080/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Kokoro-82M-bf16","input":"Hello","voice":"a"}' \
  -o output.wav
```

### STT
```bash
curl -F file=@audio.wav \
  -F model=mlx-community/whisper-large-v3-turbo \
  http://localhost:8080/v1/audio/transcriptions
```

### Web UI
Open http://localhost:7860 in browser and test each tab manually.

## Next Steps

1. Install spacy: `uv add "spacy>=3.7.0"`
2. Download language model: `uv run python -m spacy download en_core_web_sm`
3. Restart app and test TTS
4. Manual UI testing for Vision, STT, and Image Gen tabs
5. Update README with complete setup instructions
