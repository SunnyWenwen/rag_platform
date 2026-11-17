"""Offline contract and HTTP integration checks; no external service required."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import unittest
import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from contracts import IngestionDocument, ParsedDocument
from local_component import RunContext, StructuredJsonParser
from remote_adapter import RemoteApiParser
from remote_service import app

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
PAYLOAD = json.loads((HERE / "multi_page_input.json").read_text())
EXPECTED = json.loads((HERE / "multi_page_output.json").read_text())



class Contracts(unittest.TestCase):
    def test_shared_input_and_pydantic_agree(self):
        schema = json.loads((ROOT / 'schemas/ingestion_document.schema.json').read_text())
        canonical = Draft202012Validator(schema)
        advertised = Draft202012Validator(IngestionDocument.model_json_schema())
        good = [PAYLOAD, {"document_id":"a", "content":"文字"},
                {"document_id":"a", "uri":"https://example.com/file.pdf"},
                {"document_id":"a", "base64":"dGV4dA==", "media_type":"text/plain"}]
        for value in good:
            canonical.validate(value); advertised.validate(value)
            self.assertEqual(IngestionDocument.model_validate(value).to_payload(), value)
        for key in ("source_revision","content","base64","uri","media_type","schema_id","parsing_profile","metadata"):
            value=deepcopy(PAYLOAD); value[key]=None
            with self.assertRaises(Exception): canonical.validate(value)
            with self.assertRaises(Exception): advertised.validate(value)
            with self.assertRaises(ValidationError): IngestionDocument.model_validate(value)
        for value in ({"document_id":"a"}, {**PAYLOAD, "uri":"https://example.com"},
                      {**PAYLOAD, "unknown":1}, {**PAYLOAD, "content":{}},
                      {**PAYLOAD, "content":[]}, {**PAYLOAD, "document_id":1}):
            with self.assertRaises(Exception): canonical.validate(value)
            with self.assertRaises(ValidationError): IngestionDocument.model_validate(value)

    def test_canonical_units_and_output_rejections(self):
        schema=json.loads((ROOT/'schemas/parsed_document.schema.json').read_text())
        value={"document_id":"a","source_revision":"v1","units":[{"text":"A"},{"body":"B","unit_id":"optional"}],"metadata":{}}
        Draft202012Validator(schema).validate(value); ParsedDocument.model_validate(value)
        for replacement in ([], [{}], [{"text":1}]):
            bad={**value,"units":replacement}
            with self.assertRaises(Exception): Draft202012Validator(schema).validate(bad)
            with self.assertRaises(ValidationError): ParsedDocument.model_validate(bad)
        with self.assertRaises(ValidationError): ParsedDocument.model_validate({**value,"structure":{}})


class EndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_local_and_remote_have_same_output(self):
        data=IngestionDocument.model_validate(PAYLOAD)
        expected=await StructuredJsonParser().run(data,RunContext("req-1"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://parser',timeout=10) as client:
            remote=await RemoteApiParser(client,'/parse').run(data,RunContext('req-1'))
            self.assertEqual(expected.data,remote.data)
            output=remote.data[0].model_dump(mode='json')
            Draft202012Validator(json.loads((ROOT/'schemas/parsed_document.schema.json').read_text())).validate(output)
            self.assertEqual([d.model_dump(mode='json') for d in remote.data],EXPECTED)
            self.assertEqual([u['page'] for u in output['units']],[1,2])
            self.assertTrue(all('=== PAGE' not in u['text'] for u in output['units']))
            self.assertEqual(output['metadata'],PAYLOAD['metadata'])
            for payload in ({**PAYLOAD,'source_revision':None}, {**PAYLOAD,'uri':'https://example.com'}):
                self.assertEqual((await client.post('/parse',json=payload)).status_code,422)
            self.assertEqual((await client.post('/parse',json={'document_id':'a','source_revision':'v1','uri':'https://example.com/file'})).status_code,400)
            self.assertEqual((await client.post('/parse',json={'document_id':'a','content':'text'})).status_code,400)

    async def test_page_policy_and_plain_text_regression(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://parser') as client:
            for content in ("沒有頁面標記的文字", {"text":"沒有頁面標記的文字", "page":7}):
                value={"document_id":"plain","source_revision":"v1","content":content}
                local=await StructuredJsonParser().run(IngestionDocument.model_validate(value),RunContext('plain'))
                remote=(await client.post('/parse',json=value)).json()
                self.assertEqual([d.model_dump(mode='json') for d in local.data],remote)
                self.assertEqual(len(remote[0]['units']),1)
            for content in (
                {"text":"preamble\n=== PAGE 1 ===\nA"},
                {"text":"=== PAGE 1 ===\nA\n=== PAGE 1 ===\nB"},
                {"text":"=== PAGE 2 ===\nA\n=== PAGE 1 ===\nB"},
                {"text":"=== PAGE 1 ===\n \n=== PAGE 2 ===\nB"},
                {"text":PAYLOAD['content']['text'],"page":99},
            ):
                value={"document_id":"bad-page","source_revision":"v1","content":content}
                with self.assertRaises(ValueError): await StructuredJsonParser().run(IngestionDocument.model_validate(value),RunContext('bad'))
                self.assertEqual((await client.post('/parse',json=value)).status_code,400)

    async def test_adapter_forwards_only_wire_input_and_validates_response(self):
        data=IngestionDocument.model_validate(PAYLOAD)
        good=deepcopy(EXPECTED[0])
        async def valid(request):
            self.assertEqual(json.loads(request.content),PAYLOAD)
            self.assertEqual(request.headers['X-Request-ID'],'trace-1')
            return httpx.Response(200,json=[good])
        async with httpx.AsyncClient(transport=httpx.MockTransport(valid),base_url='http://parser') as client:
            await RemoteApiParser(client,'/parse').run(data,RunContext('trace-1'))
        for body in ({'units':[]}, [{**good,'document_id':'wrong'}], [{**good,'metadata':{}}], []):
            async def invalid(request): return httpx.Response(200,json=body)
            async with httpx.AsyncClient(transport=httpx.MockTransport(invalid),base_url='http://parser') as client:
                with self.assertRaises((ValueError,ValidationError)):
                    await RemoteApiParser(client,'/parse').run(data,RunContext('trace-1'))
        async def unavailable(request): return httpx.Response(503)
        async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable),base_url='http://parser') as client:
            with self.assertRaises(httpx.HTTPStatusError): await RemoteApiParser(client,'/parse').run(data,RunContext('trace-1'))


if __name__=='__main__':unittest.main(verbosity=2)

