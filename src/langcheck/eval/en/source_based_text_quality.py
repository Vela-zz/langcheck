import json
from typing import List

import nltk
import openai
import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer

from langcheck.eval.eval_value import EvalValue

_factual_consistency_model_path = 'MingZhong/unieval-fact'
_factual_consistency_config = None
_factual_consistency_tokenizer = None
_factual_consistency_model = None


def factual_consistency(generated_outputs: List[str],
                        sources: List[str],
                        model_type: str = 'local') -> EvalValue[float]:
    '''Calculates the factual consistency between the generated outputs and
    the sources. The factual consistency score for one generated output is
    computed as the average of the per-sentence consistencies of the generated
    output with the source text, where the consistency is computed by querying
    the UniEval-fact model that has been pre-trained to evaluate factual
    consistency. This metric takes on float values between [0, 1], where 0 means
    that the output is not at all consistent with the source text, and 1 means
    that the output is fully consistent with the source text.

    Ref:
        https://github.com/maszhongming/UniEval

    Args:
        generated_outputs: A list of model generated outputs to evaluate
        sources: A list of source texts

    Returns:
        An EvalValue object
    '''
    # Confirm necessary data for nltk.tokenize.sent_tokenize() exists
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    # TODO: Unify the validation that we do in all of the evaluation functions
    if len(generated_outputs) != len(sources):
        raise ValueError(
            'The generated outputs and sources lists must be of the same '
            'length')

    # The UniEval-fact model takes quite some time to download, so we early
    # return here to avoid unnecessarily downloading it
    if len(generated_outputs) == 0:
        return EvalValue(metric_name='factual_consistency',
                         prompts=None,
                         generated_outputs=[],
                         reference_outputs=[],
                         sources=[],
                         metric_values=[],
                         language='en')

    # Split the generated outputs into individual sentences. This is consistent
    # with how UniEval calculates factual consistency, where the factual
    # consistency of each generated sentence gets averaged.
    # (https://github.com/maszhongming/UniEval/blob/509075cc87bb64f239180ece460025466b260383/metric/evaluator.py#L261)
    srcs_list, gen_sentences_list = [], []
    num_sentences_list = []
    for src, gen in zip(sources, generated_outputs):
        gen_sentences = nltk.tokenize.sent_tokenize(gen)
        num_sentences_list.append(len(gen_sentences))
        gen_sentences_list += gen_sentences
        srcs_list += [src] * len(gen_sentences)

    if model_type == 'local':
        global _factual_consistency_config, _factual_consistency_tokenizer, \
            _factual_consistency_model
        if _factual_consistency_config is None:
            _factual_consistency_config = AutoConfig.from_pretrained(
                _factual_consistency_model_path)
        if _factual_consistency_tokenizer is None:
            _factual_consistency_tokenizer = AutoTokenizer.from_pretrained(
                _factual_consistency_model_path)
        if _factual_consistency_model is None:
            _factual_consistency_model = AutoModelForSeq2SeqLM.from_pretrained(
                _factual_consistency_model_path,
                config=_factual_consistency_config)
            _factual_consistency_model.eval()

        pos_id = _factual_consistency_tokenizer('Yes')['input_ids'][0]
        neg_id = _factual_consistency_tokenizer('No')['input_ids'][0]
        softmax = nn.Softmax(dim=1)

        model_input_list = []
        for src, gen in zip(srcs_list, gen_sentences_list):
            model_input = (
                f'question: Is this claim consistent with the document? </s> '
                f'claim: {gen} </s> '
                f'document: {src}')

            model_input_list.append(model_input)

        # Specifying the targets is required to run the model, but has no effect on
        # the score
        target_list = ["No" for _ in range(len(model_input_list))]

        batch_size = 8
        score_list = []
        for i in range(0, len(model_input_list), batch_size):
            inputs = model_input_list[i:i + batch_size]
            targets = target_list[i:i + batch_size]

            with torch.no_grad():
                encoded_inputs = _factual_consistency_tokenizer(
                    inputs, truncation=True, padding=True, return_tensors='pt')
                encoded_targets = _factual_consistency_tokenizer(
                    targets, truncation=True, padding=True, return_tensors='pt')
                inputs_tokens = encoded_inputs['input_ids']
                inputs_mask = encoded_inputs['attention_mask']
                targets_tokens = encoded_targets['input_ids'][:,
                                                              0].unsqueeze(-1)

                outputs = _factual_consistency_model(input_ids=inputs_tokens,
                                                     attention_mask=inputs_mask,
                                                     labels=targets_tokens)
                logits = outputs.logits.view(
                    -1, _factual_consistency_model.config.vocab_size)
                pos_score = softmax(logits)[:, pos_id]
                neg_score = softmax(logits)[:, neg_id]
                score_list += [
                    x.item() for x in pos_score / (pos_score + neg_score)
                ]
    else:  # openai
        prompt = lambda src, gen_output: f'''
        You are evaluating the factual consistency of a submitted claim. Here is the data:
        [BEGIN DATA]
        ************
        [Source]: {src}
        ************
        [Submission]: {gen_output}
        ************
        [END DATA]

        Determine whether the submitted claim is factually consistent with the source,
        and save the resulting assessment. The available assessments are:
        `Fully Consistent` - The submitted claim is fully factually consistent with the source text.
        `Partially Consistent` - The submitted claim is partially factually consistent with the source text. There are some aspects of the claim that are factually consistent, but some aspects that are not.
        `Not Consistent` - The submitted claim is not factually consistent with the source text.
        '''

        def _factuality_assessment_to_score(assessment: str) -> float:
            if assessment == 'Fully Consistent':
                return 1.0
            elif assessment == 'Partially Consistent':
                return 0.5
            elif assessment == 'Not Consistent':
                return 0.0
            else:
                # By leveraging the function calling API, this should be pretty
                # rare, but we're dealing with LLMs here so nothing is absolute!
                raise AssertionError(
                    'OpenAI returned an unrecognized factuality assessment :(')

        score_list = []
        for src, gen in zip(srcs_list, gen_sentences_list):
            messages = [{
                "role": "user",
                "content": prompt(src=src, gen_output=gen)
            }]
            functions = [{
                "name":
                    "save_factual_consistency_assessment",
                "description":
                    "Save's a submitted claim's factual consistency assessment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "factuality": {
                            "type":
                                "string",
                            "enum": [
                                "Fully Consistent", "Partially Consistent",
                                "Not Consistent"
                            ],
                            "description":
                                "The factual consistency assessment of the claim",
                        },
                    },
                    "required": ["factuality"],
                },
            }]
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                functions=functions,
                function_call={"name": "save_factual_consistency_assessment"},
            )
            response_message = response["choices"][0]["message"]
            function_args = json.loads(
                response_message["function_call"]["arguments"])
            factuality_assessment = function_args.get("factuality")
            score_list.append(
                _factuality_assessment_to_score(factuality_assessment))

    # The score for each output is the average of the scores of its sentences
    score_per_output = []
    start_idx = 0
    for num in num_sentences_list:
        score_per_output.append(
            sum(score_list[start_idx:start_idx + num]) / num)
        start_idx += num

    return EvalValue(metric_name='factual_consistency',
                     prompts=None,
                     generated_outputs=generated_outputs,
                     reference_outputs=None,
                     sources=sources,
                     metric_values=score_per_output,
                     language='en')
