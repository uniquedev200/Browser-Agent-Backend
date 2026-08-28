from __future__ import annotations

from typing import Any


def make_simple_form_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Registration Form",
            "url": "https://example.com/register",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "name_1",
                "role": "textbox",
                "label": "Full Name",
                "value": "",
                "bbox": [100, 150, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "email_1",
                "role": "textbox",
                "type": "email",
                "label": "Email",
                "value": "",
                "bbox": [100, 220, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "phone_1",
                "role": "textbox",
                "type": "tel",
                "label": "Phone",
                "value": "",
                "bbox": [100, 290, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "submit_1",
                "role": "button",
                "text": "Submit",
                "bbox": [100, 360, 120, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_multistep_form_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Internship Application - Personal Info",
            "url": "https://example.com/apply/personal",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "full_name",
                "role": "textbox",
                "label": "Full Name",
                "value": "",
                "bbox": [100, 150, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "email_field",
                "role": "textbox",
                "type": "email",
                "label": "Email",
                "value": "",
                "bbox": [100, 220, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "phone_field",
                "role": "textbox",
                "type": "tel",
                "label": "Phone",
                "value": "",
                "bbox": [100, 290, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "next_btn",
                "role": "button",
                "text": "Next",
                "bbox": [500, 700, 100, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_education_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Internship Application - Education",
            "url": "https://example.com/apply/education",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "college",
                "role": "combobox",
                "label": "College/University",
                "value": "",
                "bbox": [100, 150, 400, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "degree",
                "role": "textbox",
                "label": "Degree",
                "value": "",
                "bbox": [100, 220, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "cgpa",
                "role": "textbox",
                "label": "CGPA",
                "value": "",
                "bbox": [100, 290, 150, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "edu_next",
                "role": "button",
                "text": "Next",
                "bbox": [500, 700, 100, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_scroll_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Application Form",
            "url": "https://example.com/apply",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "name_top",
                "role": "textbox",
                "label": "Name",
                "value": "",
                "bbox": [100, 100, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "email_top",
                "role": "textbox",
                "label": "Email",
                "value": "",
                "bbox": [100, 170, 300, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_scrolled_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Application Form",
            "url": "https://example.com/apply",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 780},
        },
        "elements": [
            {
                "element_id": "name_top",
                "role": "textbox",
                "label": "Name",
                "value": "",
                "bbox": [100, 100, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "email_top",
                "role": "textbox",
                "label": "Email",
                "value": "",
                "bbox": [100, 170, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "phone_bottom",
                "role": "textbox",
                "label": "Phone",
                "value": "",
                "bbox": [100, 950, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "address_bottom",
                "role": "textbox",
                "label": "Address",
                "value": "",
                "bbox": [100, 1020, 300, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_validation_error_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Registration Form",
            "url": "https://example.com/register",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "email_field",
                "role": "textbox",
                "type": "email",
                "label": "Email",
                "value": "invalid-email",
                "bbox": [100, 150, 300, 40],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "error_banner",
                "role": "alert",
                "text": "Please enter a valid email address",
                "bbox": [100, 200, 300, 30],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "submit_btn",
                "role": "button",
                "text": "Submit",
                "bbox": [100, 250, 120, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_review_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Internship Application - Review",
            "url": "https://example.com/apply/review",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "review_name",
                "role": "text",
                "label": "Name",
                "value": "<PERSON>",
                "bbox": [100, 100, 300, 30],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "review_email",
                "role": "text",
                "label": "Email",
                "value": "<EMAIL>",
                "bbox": [100, 150, 300, 30],
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "submit_final",
                "role": "button",
                "text": "Submit Application",
                "bbox": [100, 300, 200, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }


def make_confirmation_state() -> dict[str, Any]:
    return {
        "page": {
            "title": "Application Submitted",
            "url": "https://example.com/apply/confirmation",
            "viewport": {"width": 1440, "height": 900},
            "scroll": {"x": 0, "y": 0},
        },
        "elements": [
            {
                "element_id": "confirmation_msg",
                "role": "heading",
                "text": "Your application has been submitted successfully",
                "bbox": [100, 200, 500, 40],
                "visible": True,
                "enabled": True,
            },
        ],
    }
