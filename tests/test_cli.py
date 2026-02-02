import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from typer.testing import CliRunner
from ieeA.cli import app

runner = CliRunner()


def test_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "arXiv Paper Translator" in result.stdout


def test_config_show():
    # Mock load_config to return a dummy config
    with patch("ieeA.cli.load_config") as mock_load:
        mock_config = MagicMock()
        mock_config.model_dump.return_value = {"llm": {"sdk": "test"}}
        mock_load.return_value = mock_config

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "sdk': 'test'" in result.stdout


def test_config_set(tmp_path):
    # We need to mock the CONFIG_FILE path in cli.py to use a temp file
    config_file = tmp_path / "config.yaml"
    with patch("ieeA.cli.CONFIG_FILE", config_file):
        result = runner.invoke(app, ["config", "set", "llm.sdk", "anthropic"])
        assert result.exit_code == 0
        assert "Updated llm.sdk = anthropic" in result.stdout

        # Verify file content
        import yaml

        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["llm"]["sdk"] == "anthropic"


def test_glossary_add(tmp_path):
    glossary_file = tmp_path / "glossary.yaml"
    with patch("ieeA.cli.GLOSSARY_FILE", glossary_file):
        result = runner.invoke(app, ["glossary", "add", "LLM", "大型语言模型"])
        assert result.exit_code == 0
        assert "Added term: LLM -> 大型语言模型" in result.stdout

        import yaml

        with open(glossary_file) as f:
            data = yaml.safe_load(f)
        assert data["LLM"]["target"] == "大型语言模型"


@patch("ieeA.cli.ArxivDownloader")
@patch("ieeA.cli.LaTeXParser")
@patch("ieeA.cli.TranslationPipeline")
@patch("ieeA.cli.get_sdk_client")
@patch("ieeA.cli.ValidationEngine")
@patch("ieeA.cli.LaTeXCompiler")
def test_translate_command(
    mock_compiler,
    mock_validator,
    mock_get_sdk_client,
    mock_pipeline,
    mock_parser,
    mock_downloader,
    tmp_path,
):
    # Setup mocks
    mock_downloader_instance = mock_downloader.return_value
    mock_downloader_instance.download.return_value = MagicMock(
        arxiv_id="2301.00001", main_tex=tmp_path / "main.tex"
    )

    mock_parser_instance = mock_parser.return_value
    mock_doc = MagicMock()
    mock_doc.chunks = [MagicMock(id="1", content="test")]
    mock_doc.reconstruct.return_value = "Translated Content"
    mock_parser_instance.parse_file.return_value = mock_doc

    # Mock pipeline async methods properly
    mock_pipeline_instance = mock_pipeline.return_value

    # Mock translate_document as AsyncMock
    mock_translated_chunk = MagicMock()
    mock_translated_chunk.model_dump.return_value = {
        "chunk_id": "1",
        "translation": "测试",
    }
    mock_pipeline_instance.translate_document = AsyncMock(
        return_value=[mock_translated_chunk]
    )

    # Run command
    # We use --key to provide API key so it doesn't fail
    result = runner.invoke(
        app,
        [
            "translate",
            "2301.00001",
            "--output-dir",
            str(tmp_path),
            "--no-compile",
            "--key",
            "fake-key",
        ],
    )

    assert result.exit_code == 0
    assert "Starting Job" in result.stdout
    assert "Translating..." in result.stdout
