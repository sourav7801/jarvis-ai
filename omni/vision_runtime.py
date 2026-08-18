from __future__ import annotations

from pathlib import Path

import base64
import json
import os
import shutil
import urllib.request


class VisionRuntime:

    def __init__(
        self,
        config_path=None,
        base_url=None,
    ):

        self.config_path = Path(
            config_path
            or (
                Path("config")
                / "vision_provider.json"
            )
        )


        self.base_url = (
            base_url
            or os.environ.get(
                "OLLAMA_HOST",
                "http://127.0.0.1:11434",
            )
        ).rstrip(
            "/"
        )


    def _get(
        self,
        endpoint,
        timeout=3,
    ):

        with urllib.request.urlopen(
            self.base_url
            + endpoint,

            timeout=timeout,
        ) as response:

            return json.loads(
                response.read()
                .decode(
                    "utf-8"
                )
            )


    def _post(
        self,
        endpoint,
        payload,
        timeout=10,
    ):

        request = urllib.request.Request(
            self.base_url
            + endpoint,

            data=json.dumps(
                payload
            ).encode(
                "utf-8"
            ),

            headers={
                "Content-Type":
                    "application/json"
            },

            method="POST",
        )


        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            return json.loads(
                response.read()
                .decode(
                    "utf-8"
                )
            )


    def config(
        self,
    ):

        environment_model = (
            os.environ.get(
                "JARVIS_VISION_MODEL"
            )
        )


        if environment_model:

            return {
                "provider":
                    "ollama",

                "model":
                    environment_model,

                "enabled":
                    True,
            }


        if not self.config_path.exists():

            return {
                "provider":
                    "ollama",

                "model":
                    None,

                "enabled":
                    False,
            }


        try:

            return json.loads(
                self.config_path
                .read_text(
                    encoding="utf-8"
                )
            )


        except Exception:

            return {
                "provider":
                    "ollama",

                "model":
                    None,

                "enabled":
                    False,
            }


    def models(
        self,
    ):

        try:

            data = self._get(
                "/api/tags"
            )


            return tuple(
                str(
                    item.get(
                        "name",
                        ""
                    )
                ).strip()

                for item
                in data.get(
                    "models",
                    ()
                )

                if item.get(
                    "name"
                )
            )


        except Exception:

            return ()


    def capabilities(
        self,
        model,
    ):

        try:

            data = self._post(
                "/api/show",

                {
                    "model":
                        str(
                            model
                        )
                },
            )


            return tuple(
                str(
                    capability
                ).lower()

                for capability
                in data.get(
                    "capabilities",
                    ()
                )
            )


        except Exception:

            return ()


    def is_vision_model(
        self,
        model,
    ):

        return bool(
            model

            and (
                "vision"
                in self.capabilities(
                    model
                )
            )
        )


    def status(
        self,
    ):

        config = self.config()

        model = config.get(
            "model"
        )

        installed = self.models()


        present = bool(
            model
            and model
            in installed
        )


        verified = bool(
            present
            and self.is_vision_model(
                model
            )
        )


        return {
            "provider":
                "ollama",

            "ollama_executable":
                bool(
                    shutil.which(
                        "ollama"
                    )
                ),

            "ollama_reachable":
                bool(
                    installed
                ),

            "installed_models":
                installed,

            "configured_model":
                model,

            "configured_model_present":
                present,

            "configured_model_vision_verified":
                verified,

            "enabled":
                bool(
                    config.get(
                        "enabled",
                        False,
                    )
                ),

            "vision_ready":
                bool(
                    config.get(
                        "enabled",
                        False,
                    )
                    and verified
                ),

            "automatic_model_download":
                False,

            "api_endpoint":
                "/api/chat",
        }


    def configure(
        self,
        model,
        *,
        enabled=True,
    ):

        model = str(
            model
        ).strip()


        if model not in self.models():

            raise ValueError(
                "Vision model is not installed."
            )


        if not self.is_vision_model(
            model
        ):

            raise ValueError(
                "Ollama does not report vision "
                "capability for this model."
            )


        config = {
            "provider":
                "ollama",

            "model":
                model,

            "enabled":
                bool(
                    enabled
                ),
        }


        self.config_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temporary = (
            self.config_path
            .with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                config,
                indent=2,
            ),
            encoding="utf-8",
        )


        temporary.replace(
            self.config_path
        )


        return config


    @staticmethod
    def _image(
        path,
    ):

        source = Path(
            path
        ).resolve()


        if not source.exists():

            raise FileNotFoundError(
                source
            )


        if source.suffix.lower() not in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        ):

            raise ValueError(
                "Vision input must be PNG/JPG/JPEG/WEBP."
            )


        return base64.b64encode(
            source.read_bytes()
        ).decode(
            "ascii"
        )


    def analyze(
        self,
        path,
        *,
        prompt=None,
        timeout=180,
    ):

        status = self.status()


        if not status[
            "vision_ready"
        ]:

            return {
                "success":
                    False,

                "vision_available":
                    False,

                "error":
                    (
                        "No verified vision-capable "
                        "model is configured."
                    ),

                "status":
                    status,
            }


        request_prompt = str(
            prompt
            or (
                "Analyze this computer screenshot. "
                "Return JSON only with keys summary, "
                "visible_text and elements. "
                "elements must be an array. "
                "Each element should contain label, "
                "role, x, y and confidence."
            )
        )


        payload = {
            "model":
                status[
                    "configured_model"
                ],

            "messages": [
                {
                    "role":
                        "user",

                    "content":
                        request_prompt,

                    "images": [
                        self._image(
                            path
                        )
                    ],
                }
            ],

            "stream":
                False,

            "format": {
                "type":
                    "object",

                "properties": {
                    "summary": {
                        "type":
                            "string"
                    },

                    "visible_text": {
                        "type":
                            "array",

                        "items": {
                            "type":
                                "string"
                        }
                    },

                    "elements": {
                        "type":
                            "array",

                        "items": {
                            "type":
                                "object",

                            "properties": {
                                "label": {
                                    "type":
                                        "string"
                                },

                                "role": {
                                    "type":
                                        "string"
                                },

                                "x": {
                                    "type":
                                        "number"
                                },

                                "y": {
                                    "type":
                                        "number"
                                },

                                "confidence": {
                                    "type":
                                        "number"
                                }
                            },

                            "required": [
                                "label",
                                "role",
                                "confidence"
                            ]
                        }
                    }
                },

                "required": [
                    "summary",
                    "visible_text",
                    "elements"
                ]
            },

            "keep_alive":
                "10m",
        }


        try:

            data = self._post(
                "/api/chat",

                payload,

                timeout=
                    timeout,
            )


            message = data.get(
                "message",
                {}
            )


            raw = str(
                message.get(
                    "content",
                    ""
                )
            )


            try:

                parsed = json.loads(
                    raw
                )

            except Exception:

                parsed = {
                    "summary":
                        raw[:12000],

                    "visible_text":
                        [],

                    "elements":
                        [],
                }


            if not isinstance(
                parsed,
                dict,
            ):

                parsed = {
                    "summary":
                        str(
                            parsed
                        )[:12000],

                    "visible_text":
                        [],

                    "elements":
                        [],
                }


            if not isinstance(
                parsed.get(
                    "elements",
                    []
                ),
                list,
            ):

                parsed[
                    "elements"
                ] = []


            return {
                "success":
                    True,

                "vision_available":
                    True,

                "model":
                    status[
                        "configured_model"
                    ],

                "analysis":
                    parsed,

                "usage": {
                    "prompt_eval_count":
                        data.get(
                            "prompt_eval_count"
                        ),

                    "eval_count":
                        data.get(
                            "eval_count"
                        ),

                    "total_duration":
                        data.get(
                            "total_duration"
                        ),
                },
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "vision_available":
                    True,

                "model":
                    status[
                        "configured_model"
                    ],

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),
            }


vision_runtime = (
    VisionRuntime()
)
