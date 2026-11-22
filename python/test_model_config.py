import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv
from model_config import gateway_url, openai_chat_options, required_api_keys


class ModelConfigTests(unittest.TestCase):
    def test_direct_modes_require_only_openai_for_chat(self):
        for flag in (None, "", "false", "FALSE", "0", "no"):
            env = {"OPENAI_API_KEY": "provider-key"}
            if flag is not None:
                env["LANGSMITH_GATEWAY"] = flag
            with self.subTest(flag=flag):
                self.assertIsNone(gateway_url(env))
                self.assertEqual(openai_chat_options(env), {"api_key": "provider-key"})
                self.assertEqual(required_api_keys(env), ["OPENAI_API_KEY"])

    def test_gateway_modes_use_langsmith_not_provider_key(self):
        for flag in ("true", "TRUE", "1", "yes", "YeS"):
            env = {"LANGSMITH_GATEWAY": flag, "LANGSMITH_API_KEY": "ls-key"}
            with self.subTest(flag=flag):
                options = openai_chat_options(env)
                self.assertEqual(options["api_key"], "ls-key")
                self.assertEqual(
                    options["base_url"], "https://gateway.smith.langchain.com/openai/v1"
                )
                self.assertEqual(required_api_keys(env), ["LANGSMITH_API_KEY"])

    def test_custom_url_and_override_are_independent_of_tracing(self):
        env = {
            "LANGSMITH_GATEWAY": "http://localhost:8080/custom/",
            "LANGSMITH_GATEWAY_API_KEY": "inference-key",
            "LANGSMITH_API_KEY": "tracing-key",
            "LANGSMITH_TRACING": "false",
        }
        self.assertEqual(
            openai_chat_options(env),
            {
                "api_key": "inference-key",
                "base_url": "http://localhost:8080/custom/openai/v1",
            },
        )
        self.assertEqual(required_api_keys(env), ["LANGSMITH_GATEWAY_API_KEY"])
        env["LANGSMITH_TRACING"] = "true"
        self.assertEqual(
            required_api_keys(env), ["LANGSMITH_GATEWAY_API_KEY", "LANGSMITH_API_KEY"]
        )
        env["LANGSMITH_GATEWAY_API_KEY"] = ""
        self.assertEqual(openai_chat_options(env)["api_key"], "tracing-key")

    def test_missing_empty_and_placeholder_credentials_fail(self):
        for flag, key in (("false", "OPENAI_API_KEY"), ("true", "LANGSMITH_API_KEY")):
            for value in (
                None,
                "",
                " ",
                "your_api_key_here",
                "sk-proj-...",
                "lsv2_pt_...",
                "your-openai-api-key",
                "your-langsmith-key",
                "****",
                "<api-key>",
                "changeme",
                "placeholder",
            ):
                env = {"LANGSMITH_GATEWAY": flag}
                if value is not None:
                    env[key] = value
                with (
                    self.subTest(flag=flag, value=value),
                    self.assertRaisesRegex(ValueError, key),
                ):
                    openai_chat_options(env)
        with self.assertRaisesRegex(ValueError, "LANGSMITH_GATEWAY_API_KEY"):
            openai_chat_options(
                {
                    "LANGSMITH_GATEWAY": "true",
                    "LANGSMITH_GATEWAY_API_KEY": "your_key_here",
                    "LANGSMITH_API_KEY": "valid-key",
                }
            )

    def test_checker_uses_selected_keys_even_when_override_is_not_in_template(self):
        import env_utils

        example = str(Path(__file__).with_name("example.env"))
        env = {
            "LANGSMITH_GATEWAY": "true",
            "LANGSMITH_GATEWAY_API_KEY": "inference-key",
            "LANGSMITH_TRACING": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                env_utils.doublecheck_env(example)
                env_utils.check_env_file_exists("missing-course-env-file", example)
            self.assertNotIn("Issues found:", output.getvalue())
            self.assertIn("all required variables are set", output.getvalue())
            os.environ["LANGSMITH_GATEWAY_API_KEY"] = "your_key_here"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                env_utils.doublecheck_env(example)
            self.assertIn("LANGSMITH_GATEWAY_API_KEY still has", output.getvalue())
            self.assertNotIn("OPENAI_API_KEY is required", output.getvalue())
            os.environ["LANGSMITH_GATEWAY_API_KEY"] = "inference-key"
            os.environ["LANGSMITH_TRACING"] = "true"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                env_utils.doublecheck_env(example)
            self.assertIn("LANGSMITH_API_KEY is required", output.getvalue())

    def test_dotenv_and_shell_precedence_match_checker(self):
        import env_utils

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {}, clear=True),
        ):
            env_file = Path(folder) / ".env"
            env_file.write_text(
                "LANGSMITH_GATEWAY=true\nLANGSMITH_API_KEY=file-key\nLANGSMITH_TRACING=false\n"
            )
            load_dotenv(env_file)
            self.assertEqual(openai_chat_options()["api_key"], "file-key")
            required = env_utils._parse_required_keys(
                str(Path(__file__).with_name("example.env"))
            )
            self.assertEqual(list(required), ["LANGSMITH_API_KEY"])
            os.environ["LANGSMITH_GATEWAY"] = "false"
            os.environ["OPENAI_API_KEY"] = "shell-key"
            load_dotenv(env_file)
            self.assertEqual(openai_chat_options(), {"api_key": "shell-key"})
            output = io.StringIO()
            os.environ["OPENAI_API_KEY"] = ""
            with contextlib.redirect_stdout(output):
                env_utils.doublecheck_env(str(Path(__file__).with_name("example.env")))
            self.assertIn("Issues found:", output.getvalue())
            self.assertIn("OPENAI_API_KEY still has", output.getvalue())

    def test_capstone_chat_uses_gateway_and_embeddings_remain_direct(self):
        import sys

        root = Path(__file__).parent
        folder = root / "capstone/conversation_agents"
        env = {
            "LANGSMITH_GATEWAY": "true",
            "LANGSMITH_API_KEY": "ls-key",
            "LANGSMITH_TRACING": "false",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch("dotenv.load_dotenv"),
            patch.object(sys, "path", [str(folder), *sys.path]),
        ):
            spec = importlib.util.spec_from_file_location(
                "capstone_runner", folder / "test_conversation.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.client.api_key, "ls-key")
            self.assertEqual(
                str(module.client.base_url),
                "https://gateway.smith.langchain.com/openai/v1/",
            )
            os.environ["OPENAI_API_KEY"] = "embedding-key"
            direct = module.AsyncOpenAI()
            self.assertEqual(direct.api_key, "embedding-key")
            self.assertEqual(str(direct.base_url), "https://api.openai.com/v1/")
            self.assertIn(
                "KnowledgeBase(AsyncOpenAI())",
                (folder / "test_conversation.py").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
