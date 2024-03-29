import json
from unittest import mock
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app
from src.local_secrets import SECRETS_TYPEFORM_CLIENT_SECRET, SECRETS_DATAVERSE_PARENT_ALIAS
from src.utils import format_form_response_to_dataset

client = TestClient(app)


@mock.patch("pyDataverse.api.NativeApi.create_dataset")
@mock.patch("pyDataverse.models.Dataset.from_json")
@mock.patch("pyDataverse.models.Dataset.json")
def test_submit_dataset_form(dataset_to_json_mock, dataset_from_json_mock, create_dataset_mock):
    # no input data => failure, no processable entity
    response = client.post("/submit_dataset_form")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    create_dataset_mock.assert_not_called()

    # add input data, no signature => failure, not permitted
    input_data = {"test_key": "test_value"}
    response = client.post("/submit_dataset_form", json=input_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Invalid signature token."}
    dataset_from_json_mock.assert_not_called()
    create_dataset_mock.assert_not_called()

    # Wrong signature => failure, not permitted
    headers = {"typeform-signature": "test"}
    response = client.post("/submit_dataset_form", json=input_data, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {"detail": "Invalid signature token."}
    dataset_from_json_mock.assert_not_called()
    create_dataset_mock.assert_not_called()

    # Right signature, required fields aren't there => failure, validation error
    headers["typeform-signature"] = SECRETS_TYPEFORM_CLIENT_SECRET
    response = client.post("/submit_dataset_form", json=input_data, headers=headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": f"Field 'Назва джерела' is required."}
    dataset_from_json_mock.assert_not_called()
    create_dataset_mock.assert_not_called()

    # Required fields are there => success
    required_fields = ["Назва джерела", "Автор джерела", "Опис українською"]
    input_data = {
        field_: "test" for field_ in required_fields
    }
    expected_success_result = create_dataset_mock.return_value.json.return_value = {
        "dataset": "test"
    }
    response = client.post("/submit_dataset_form", json=input_data, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == expected_success_result

    dataset_from_json_mock.assert_called_once_with(
        json.dumps(format_form_response_to_dataset(input_data))
    )
    create_dataset_mock.assert_called_once_with(SECRETS_DATAVERSE_PARENT_ALIAS, dataset_to_json_mock.return_value)
