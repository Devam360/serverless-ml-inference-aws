# Lambda container. scikit-learn and its wheels are a poor fit for a zip
# package. The model artifact is not copied into the image: the function
# downloads it from S3 on cold start (MODEL_BUCKET and MODEL_KEY). For a
# local container demo, mount the artifact and set MODEL_PATH.
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY src/housing_api ${LAMBDA_TASK_ROOT}/housing_api

CMD ["housing_api.handler.handler"]
