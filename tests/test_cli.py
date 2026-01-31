import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from ieet.cli import app

runner = CliRunner()

def test_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ieeT - IEEE/arXiv Translator CLI" in result.stdout

def test_config_show():
    # Mock load_config to return a dummy config
    with patch("ieet.cli.load_config") as mock_load:
        mock_config = MagicMock()
        mock_config.model_dump.return_value = {"llm": {"provider": "test"}}
        mock_load.return_value = mock_config
        
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "provider': 'test'" in result.stdout

def test_config_set(tmp_path):
    # We need to mock the CONFIG_FILE path in cli.py to use a temp file
    config_file = tmp_path / "config.yaml"
    with patch("ieet.cli.CONFIG_FILE", config_file):
        result = runner.invoke(app, ["config", "set", "llm.provider", "claude"])
        assert result.exit_code == 0
        assert "Updated llm.provider = claude" in result.stdout
        
        # Verify file content
        import yaml
        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert data["llm"]["provider"] == "claude"

def test_glossary_add(tmp_path):
    glossary_file = tmp_path / "glossary.yaml"
    with patch("ieet.cli.GLOSSARY_FILE", glossary_file):
        result = runner.invoke(app, ["glossary", "add", "LLM", "大型语言模型"])
        assert result.exit_code == 0
        assert "Added term: LLM -> 大型语言模型" in result.stdout
        
        import yaml
        with open(glossary_file) as f:
            data = yaml.safe_load(f)
        assert data["LLM"]["target"] == "大型语言模型"

@patch("ieet.cli.ArxivDownloader")
@patch("ieet.cli.LaTeXParser")
@patch("ieet.cli.TranslationPipeline")
@patch("ieet.cli.get_provider")
@patch("ieet.cli.ValidationEngine")
@patch("ieet.cli.TeXCompiler")
def test_translate_command(
    mock_compiler, mock_validator, mock_get_provider, 
    mock_pipeline, mock_parser, mock_downloader, tmp_path
):
    # Setup mocks
    mock_downloader_instance = mock_downloader.return_value
    mock_downloader_instance.download.return_value = MagicMock(
        arxiv_id="2301.00001",
        main_tex=tmp_path / "main.tex"
    )
    
    mock_parser_instance = mock_parser.return_value
    mock_doc = MagicMock()
    mock_doc.chunks = [MagicMock(id="1", content="test")]
    mock_doc.reconstruct.return_value = "Translated Content"
    mock_parser_instance.parse_file.return_value = mock_doc
    
    # Mock pipeline async methods
    # Since run_pipeline is async and calls pipeline methods
    mock_pipeline_instance = mock_pipeline.return_value
    # We mock _load_state to return empty
    mock_pipeline_instance._load_state.return_value = {"completed": [], "results": []}
    
    # Mock translate_chunk to return an object with model_dump
    async def async_translate(*args, **kwargs):
        res = MagicMock()
        res.model_dump.return_value = {"chunk_id": "1", "translation": "测试"}
        return res
    mock_pipeline_instance.translate_chunk.side_effect = async_translate
    
    # Run command
    # We use env var to mock API key so it doesn't fail
    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
        result = runner.invoke(app, ["translate", "2301.00001", "--output", str(tmp_path), "--no-compile"])
    
    assert result.exit_code == 0
    assert "Starting Job" in result.stdout
    assert "Translating..." in result.stdout
