# Copilot Instructions

## Project Overview

This project is a Flask-based web application for detecting and classifying the risk of offshore transactions in financial data. It processes incoming and outgoing transaction Excel files, analyzes each transaction for offshore risk, and produces annotated Excel reports with detailed risk assessments.

The application is containerized using Docker and managed with `docker-compose.yml`.

## Key Files and Directories

- `offshore_detector/app.py`: The main Flask application file. It handles file uploads, starts the processing thread, and serves the download links.
- `offshore_detector/offshore_detector.py`: The core logic for processing transactions. It orchestrates the analysis by calling other modules.
- `offshore_detector/analyzer.py`: Contains the logic for analyzing individual transactions for offshore risk.
- `offshore_detector/ai_classifier.py`: Uses an AI model to classify the risk of transactions.
- `offshore_detector/excel_handler.py`: Handles reading and writing of Excel files.
- `offshore_detector/fuzzy_matcher.py`: Implements fuzzy string matching to identify offshore-related entities.
- `offshore_detector/web_research.py`: Performs web research to gather more information about entities involved in transactions.
- `offshore_detector/config.py`: Contains configuration and constants, such as offshore jurisdictions and API keys.
- `offshore_detector/templates/index.html`: The main HTML template for the web interface.
- `Dockerfile`: Defines the Docker image for the application.
- `docker-compose.yml`: Defines the services, networks, and volumes for the Docker application.

## Developer Workflows

### Running the Application

To run the application locally, use Docker Compose:

```bash
docker-compose up --build
```

The application will be available at `http://localhost:8081`.

### File Processing

The file processing is handled asynchronously in a separate thread. The `process_transactions_wrapper` function in `app.py` is the entry point for the processing. It calls the `process_transactions` function in `offshore_detector.py` to perform the actual analysis.

The status of the processing job is stored in an in-memory dictionary. For a production environment, a more robust solution like Redis should be used.

## Conventions

- **Configuration**: Configuration is managed through environment variables. A `.env` file is used to store these variables locally. See `.env.example` for the required variables.
- **Dependencies**: Python dependencies are managed in `requirements.txt`.
- **Styling**: The project follows the PEP 8 style guide for Python code.

## Integration Points

- **OpenAI API**: The `ai_classifier.py` module uses the OpenAI API to classify transactions. The API key is configured through the `OPENAI_API_KEY` environment variable.
- **Web Research**: The `web_research.py` module performs web searches to gather information. The implementation of this module is not shown in the provided context.
