from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest
from openai.types.chat import ChatCompletion

from langcheck.augment.en import rephrase
from langcheck.metrics.eval_clients import (
    AzureOpenAIEvalClient,
    OpenAIEvalClient,
)


@pytest.mark.parametrize(
    "instances, num_perturbations, expected",
    [
        (
            "List three representative testing methods for LLMs.",
            1,
            ["Identify three typical methods used for evaluating LLMs."],
        ),
        (
            ["List three representative testing methods for LLMs."],
            2,
            [
                "Identify three typical methods used for evaluating LLMs.",
                "Identify three typical methods used for evaluating LLMs.",
            ],
        ),
    ],
)
def test_rephrase(
    instances: list[str] | str, num_perturbations: int, expected: list[str]
):
    mock_chat_completion = Mock(spec=ChatCompletion)
    mock_chat_completion.choices = [
        Mock(
            message=Mock(
                content="Identify three typical methods used for evaluating LLMs."
            )
        )
    ]
    # Calling the openai.ChatCompletion.create method requires an OpenAI API
    # key, so we mock the return value instead
    with patch(
        "openai.resources.chat.Completions.create",
        return_value=mock_chat_completion,
    ):
        # Set the necessary env vars for the 'openai' model type
        os.environ["OPENAI_API_KEY"] = "dummy_key"
        openai_client = OpenAIEvalClient()
        actual = rephrase(
            instances,
            num_perturbations=num_perturbations,
            eval_client=openai_client,
        )
        assert actual == expected

        # Set the necessary env vars for the 'azure_openai' model type
        os.environ["AZURE_OPENAI_KEY"] = "dummy_azure_key"
        os.environ["OPENAI_API_VERSION"] = "dummy_version"
        os.environ["AZURE_OPENAI_ENDPOINT"] = "dummy_endpoint"
        azure_openai_client = AzureOpenAIEvalClient(
            embedding_model_name="foo bar"
        )
        actual = rephrase(
            instances,
            num_perturbations=num_perturbations,
            eval_client=azure_openai_client,
        )
        assert actual == expected
