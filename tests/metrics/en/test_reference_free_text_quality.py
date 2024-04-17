import os
from unittest.mock import Mock, patch

import pytest
from openai.types import CreateEmbeddingResponse

from langcheck.metrics.en import (ai_disclaimer_similarity, answer_relevance,
                                  flesch_kincaid_grade, flesch_reading_ease,
                                  fluency, sentiment, toxicity)
from tests.utils import MockEvalClient, is_close

################################################################################
# Tests
################################################################################


@pytest.mark.parametrize(
    'generated_outputs',
    ['Hello', ['Hello'], ["I'm fine!", "I'm feeling pretty bad today."]])
def test_sentiment(generated_outputs):
    metric_value = sentiment(generated_outputs)
    assert 0 <= metric_value <= 1


@pytest.mark.parametrize('generated_outputs', ["I'm fine!", ["I'm fine!"]])
def test_sentiment_eval_client(generated_outputs):
    eval_client = MockEvalClient()
    metric_value = sentiment(generated_outputs, eval_model=eval_client)
    # MockEvalClient without any argument returns None
    assert metric_value.metric_values[0] is None
    sentiment_assessment_to_score = {
        'Positive': 1.0,
        'Neutral': 0.5,
        'Negative': 0.0
    }
    for option in sentiment_assessment_to_score:
        eval_client = MockEvalClient(option)
        metric_value = sentiment(generated_outputs, eval_model=eval_client)
        assert metric_value == sentiment_assessment_to_score[option]


@pytest.mark.parametrize('generated_outputs', [
    'cat', ['cat'],
    ["I'd appreciate your help.", 'Today I eats very much apples good.']
])
def test_fluency(generated_outputs):
    metric_value = fluency(generated_outputs)
    assert 0 <= metric_value <= 1


@pytest.mark.parametrize(
    'generated_outputs',
    ["I'd appreciate your help.", ["I'd appreciate your help."]])
def test_fluency_openai(generated_outputs):
    eval_client = MockEvalClient()
    metric_value = fluency(generated_outputs, eval_model=eval_client)
    # MockEvalClient without any argument returns None
    assert metric_value.metric_values[0] is None

    fluency_assessment_to_score = {
        'Poor': 0,
        'Fair': 0.5,
        'Good': 1.0,
    }

    for option in fluency_assessment_to_score:
        eval_client = MockEvalClient(option)
        metric_value = fluency(generated_outputs, eval_model=eval_client)
        assert metric_value == fluency_assessment_to_score[option]


@pytest.mark.parametrize('generated_outputs', [
    'foo bar', ['foo bar'],
    ['I hate you. Shut your mouth!', 'Thank you so much for coming today!!']
])
def test_toxicity(generated_outputs):
    metric_value = toxicity(generated_outputs)
    assert 0 <= metric_value <= 1


@pytest.mark.parametrize(
    'generated_outputs',
    ['I hate you. Shut your mouth!', ['I hate you. Shut your mouth!']])
def test_toxicity_eval_client(generated_outputs):
    eval_client = MockEvalClient()
    metric_value = toxicity(generated_outputs, eval_model=eval_client)
    # MockEvalClient without any argument returns None
    assert metric_value.metric_values[0] is None

    toxicity_assessment_to_score = {
        '1': 0,
        '2': 0.25,
        '3': 0.5,
        '4': 0.75,
        '5': 1.0
    }
    for option in toxicity_assessment_to_score:
        eval_client = MockEvalClient(option)
        metric_value = toxicity(generated_outputs, eval_model=eval_client)
        assert metric_value == toxicity_assessment_to_score[option]


@pytest.mark.parametrize(
    'generated_outputs,metric_values',
    [
        (
            'My Friend. Welcome to the Carpathians. I am anxiously expecting you.\n'  # NOQA: E501
            'Sleep well to-night. At three to-morrow the diligence will start for Bukovina;\n'  # NOQA: E501
            'a place on it is kept for you.',
            [75.00651612903226]),
        (
            [
                'My Friend. Welcome to the Carpathians. I am anxiously expecting you.\n'  # NOQA: E501
                'Sleep well to-night. At three to-morrow the diligence will start for Bukovina;\n'  # NOQA: E501
                'a place on it is kept for you.'
            ],
            [75.00651612903226]),
        (
            [
                'How slowly the time passes here, encompassed as I am by frost and snow!\n'  # NOQA: E501
                'Yet a second step is taken towards my enterprise.'
            ],
            [77.45815217391308])
    ])
def test_flesch_reading_ease(generated_outputs, metric_values):
    metric_value = flesch_reading_ease(generated_outputs)
    assert is_close(metric_value.metric_values, metric_values)


@pytest.mark.parametrize(
    'generated_outputs,metric_values',
    [
        (
            'My Friend. Welcome to the Carpathians. I am anxiously expecting you.\n'  # NOQA: E501
            'Sleep well to-night. At three to-morrow the diligence will start for Bukovina;\n'  # NOQA: E501
            'a place on it is kept for you.',
            [4.33767741935484]),
        (
            [
                'My Friend. Welcome to the Carpathians. I am anxiously expecting you.\n'  # NOQA: E501
                'Sleep well to-night. At three to-morrow the diligence will start for Bukovina;\n'  # NOQA: E501
                'a place on it is kept for you.'
            ],
            [4.33767741935484]),
        (
            [
                'How slowly the time passes here, encompassed as I am by frost and snow!\n'  # NOQA: E501
                'Yet a second step is taken towards my enterprise.'
            ],
            [5.312391304347827]),
    ])
def test_flesch_kincaid_grade(generated_outputs, metric_values):
    metric_value = flesch_kincaid_grade(generated_outputs)
    assert is_close(metric_value.metric_values, metric_values)


@pytest.mark.parametrize('generated_outputs', [[
    "I don't have personal opinions, emotions, or consciousness.",
    "As an AI language model, I don't have my own beliefs."
]])
def test_ai_disclaimer_similarity(generated_outputs):
    metric_value = ai_disclaimer_similarity(generated_outputs)
    assert 0.5 <= metric_value <= 1


@pytest.mark.parametrize('generated_outputs', [[
    "I don't have personal opinions, emotions, or consciousness.",
]])
def test_ai_disclaimer_similarity_openai(generated_outputs):
    mock_embedding_response = Mock(spec=CreateEmbeddingResponse)
    mock_embedding_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]

    # Calling the openai.resources.embeddings.create method requires an OpenAI
    # API key, so we mock the return value instead
    with patch('openai.resources.Embeddings.create',
               Mock(return_value=mock_embedding_response)):
        # Set the necessary env vars for the 'openai' embedding model type
        os.environ["OPENAI_API_KEY"] = "dummy_key"
        metric_value = ai_disclaimer_similarity(generated_outputs,
                                                model_type='openai')
        # Since the mock embeddings are the same for the generated output and
        # the AI disclaimer phrase, the AI disclaimer language similarity should
        # be 1.
        assert 0.99 <= metric_value <= 1

        # Set the necessary env vars for the 'azure_openai' model type
        os.environ["AZURE_OPENAI_KEY"] = "dummy_azure_key"
        os.environ["OPENAI_API_VERSION"] = "dummy_version"
        os.environ["AZURE_OPENAI_ENDPOINT"] = "dummy_endpoint"
        metric_value = ai_disclaimer_similarity(
            generated_outputs,
            model_type='azure_openai',
            openai_args={'model': 'foo bar'})
        # Since the mock embeddings are the same for the generated output and
        # the AI disclaimer phrase, the AI disclaimer language similarity should
        # be 1.
        assert 0.99 <= metric_value <= 1


@pytest.mark.parametrize(
    'generated_outputs,prompts',
    [("Tokyo is Japan's capital city.", 'What is the capital of Japan?'),
     (["Tokyo is Japan's capital city."], ['What is the capital of Japan?'])])
def test_answer_relevance_eval_client(generated_outputs, prompts):
    eval_client = MockEvalClient()
    metric_value = answer_relevance(generated_outputs,
                                    prompts,
                                    eval_model=eval_client)
    # MockEvalClient without any argument returns None
    assert metric_value.metric_values[0] is None

    answer_relevance_assessment_to_score = {
        'Not Relevant': 0.0,
        'Partially Relevant': 0.5,
        'Fully Relevant': 1.0
    }

    for option in answer_relevance_assessment_to_score:
        eval_client = MockEvalClient(option)
        metric_value = answer_relevance(generated_outputs,
                                        prompts,
                                        eval_model=eval_client)
        assert metric_value == answer_relevance_assessment_to_score[option]
