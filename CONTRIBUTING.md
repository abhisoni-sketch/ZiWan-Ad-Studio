# Contributing to ZiWan - Ad Studio

First off, thank you for considering contributing to ZiWan - Ad Studio! It's people like you that make the open-source community such a great place to learn, inspire, and create.

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally: `git clone https://github.com/YOUR-USERNAME/ad-creator-studio.git`
3. **Set up the environment:**
   - Navigate into the directory and copy `.env.example` to `.env`. Fill in your GCP project credentials.
   - Install dependencies: `pip install -r requirements.txt`
4. **Create a branch** for your feature or bugfix: `git checkout -b feature/amazing-new-idea`

## Making Changes

- Ensure your code follows the existing architecture patterns outlined in `ARCHITECTURE.md`.
- If you are modifying Gemini prompts or Veo AI guardrails, please test thoroughly against the included `sample_dataset/` to ensure no regressions in video physics.
- Update the documentation (like `TECHNICAL_DOSSIER.md` or `AI_GUARDRAILS_AND_PROMPT_ENGINEERING.md`) if you introduce new system behaviors.

## Submitting a Pull Request

1. Push your branch to your fork on GitHub.
2. Open a Pull Request against the `main` branch of this repository.
3. Provide a clear and detailed description of the changes you've made, the problem it solves, and any testing you've done.

We look forward to reviewing your contributions!
