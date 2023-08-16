from typing import List, Optional

from langcheck.eval.eval_value import EvalValue


def is_float(generated_outputs: List[str], min: Optional[float],
             max: Optional[float]) -> EvalValue:
    '''Checks if generated outputs can be parsed as floating point numbers,
    optionally within a min/max range. This metric is 0 or 1.

    Args:
        generated_outputs: A list of model generated outputs to evaluate
        min: The optional minimum valid float
        max: The optional maximum valid float

    Returns:
        An EvalValue object
    '''
    # The values are binary: 1 for success and 0 for failure
    metric_values = []
    for output in generated_outputs:
        try:
            output_float = float(output)
            if min is None and max is None:
                metric_values.append(1)
            elif min is not None and output_float < min:
                metric_values.append(0)
            elif max is not None and output_float > max:
                metric_values.append(0)
            else:
                metric_values.append(1)
        except:
            metric_values.append(0)

    return EvalValue(metric_name='is_float',
                     prompts=None,
                     generated_outputs=generated_outputs,
                     reference_outputs=None,
                     metric_values=metric_values)
