#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@File    :   zhipuai_llm.py
@Time    :   2023/10/16 22:06:26
@Author  :   0-yy-0
@Version :   1.0
@Contact :   310484121@qq.com
@License :   (C)Copyright 2017-2018, Liugroup-NLPR-CASIA
@Desc    :   基于智谱 AI 大模型自定义 LLM 类
'''

from __future__ import annotations

import logging
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
)

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import LLM
from langchain.pydantic_v1 import Field, root_validator
from langchain.schema.output import GenerationChunk
from langchain.utils import get_from_dict_or_env
from self_llm import Self_LLM

logger = logging.getLogger(__name__)


class ZhipuAILLM(Self_LLM):
    """Zhipuai hosted open source or customized models.

    To use, you should have the ``zhipuai`` python package installed, and
    the environment variable ``zhipuai_api_key`` set with
    your API key and Secret Key.

    zhipuai_api_key are required parameters which you could get from
    https://open.bigmodel.cn/usercenter/apikeys

    Example:
        .. code-block:: python

            from langchain.llms import ZhipuAILLM
            zhipuai_model = ZhipuAILLM(model="chatglm_turbo", temperature=temperature)

    """

    model_kwargs: Dict[str, Any] = Field(default_factory=dict)

    client: Any

    model: str = "chatglm_turbo"

    zhipuai_api_key: Optional[str] = None

    incremental: Optional[bool] = True
    """Whether to incremental the results or not."""

    streaming: Optional[bool] = False
    """Whether to streaming the results or not."""
    # streaming = -incremental

    request_timeout: Optional[int] = 60
    """request timeout for chat http requests"""

    top_p: Optional[float] = 0.8
    temperature: Optional[float] = 0.95
    request_id: Optional[float] = None

    @root_validator()
    def validate_enviroment(cls, values: Dict) -> Dict:

        values["zhipuai_api_key"] = get_from_dict_or_env(
            values,
            "zhipuai_api_key",
            "ZHIPUAI_API_KEY",
        )

        params = {
            "zhipuai_api_key": values["zhipuai_api_key"],
            "model": values["model"],
        }
        try:
            import zhipuai

            zhipuai.api_key = values["zhipuai_api_key"]
            values["client"] = zhipuai.model_api
        except ImportError:
            raise ValueError(
                "zhipuai package not found, please install it with "
                "`pip install zhipuai`"
            )
        return values

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            **{"model": self.model},
            **super()._identifying_params,
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "zhipuai"

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get the default parameters for calling OpenAI API."""
        normal_params = {
            "streaming": self.streaming,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "request_id": self.request_id,
        }

        return {**normal_params, **self.model_kwargs}

    def _convert_prompt_msg_params(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> dict:
        return {
            **{"prompt": prompt, "model": self.model},
            **self._default_params,
            **kwargs,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call out to an zhipuai models endpoint for each generation with a prompt.
        Args:
            prompt: The prompt to pass into the model.
        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python
                response = zhipuai_model("Tell me a joke.")
        """
        if self.streaming:
            completion = ""
            for chunk in self._stream(prompt, stop, run_manager, **kwargs):
                completion += chunk.text
            return completion
        params = self._convert_prompt_msg_params(prompt, **kwargs)

        response_payload = self.client.invoke(**params)
        return response_payload["data"]["choices"][-1]["content"].strip('"').strip(" ")

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        if self.streaming:
            completion = ""
            async for chunk in self._astream(prompt, stop, run_manager, **kwargs):
                completion += chunk.text
            return completion

        params = self._convert_prompt_msg_params(prompt, **kwargs)

        response = await self.client.async_invoke(**params)

        return response_payload

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        params = self._convert_prompt_msg_params(prompt, **kwargs)

        for res in self.client.invoke(**params):
            if res:
                chunk = GenerationChunk(text=res)
                yield chunk
                if run_manager:
                    run_manager.on_llm_new_token(chunk.text)

    async def _astream(

        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[GenerationChunk]:
        params = self._convert_prompt_msg_params(prompt, **kwargs)

        async for res in await self.client.ado(**params):
            if res:
                chunk = GenerationChunk(text=res["data"]["choices"]["content"])

                yield chunk
                if run_manager:
                    await run_manager.on_llm_new_token(chunk.text)
