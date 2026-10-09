import io
import fitz
from fastapi.testclient import TestClient
from app.main import app, numbers

client = TestClient(app)

def pdf_bytes(text="Revenue reached 42 million dollars in 2024. ProofLayer tracks source evidence."):
    d=fitz.open();p=d.new_page();p.insert_text((72,72),text);b=d.tobytes();d.close();return b

def test_invalid_upload_rejected():
    r=client.post('/api/documents',files={'file':('not.pdf',b'not pdf','application/pdf')})
    assert r.status_code==415

def test_extract_pages_and_answer_and_report():
    r=client.post('/api/documents',files={'file':('test.pdf',pdf_bytes(),'application/pdf')})
    assert r.status_code==200, r.text
    doc=r.json(); assert doc['page_count']==1
    pdf=client.get(f"/api/documents/{doc['id']}/file")
    assert pdf.status_code==200
    assert pdf.headers['content-type']=='application/pdf'
    assert pdf.headers['content-disposition'].startswith('inline;')
    assert pdf.content.startswith(b'%PDF-')
    page=client.get(f"/api/documents/{doc['id']}/pages/1").json()
    assert '42 million' in page['text']
    q=client.post('/api/questions',json={'document_id':doc['id'],'question':'What was revenue in 2024?'})
    assert q.status_code==200, q.text
    body=q.json(); assert body['evidence'] and body['evidence'][0]['page']==1
    assert body['claims']
    evidence_by_id={item['id']:item for item in body['evidence']}
    for claim in body['claims']:
        for citation in claim['evidence_ids']:
            assert citation in evidence_by_id
        assert set(claim['pages']) <= {item['page'] for item in body['evidence']}
    assert client.get(f"/api/reports/{body['id']}/export").status_code==200
    no=client.post('/api/questions',json={'document_id':doc['id'],'question':'What is the capital of Mars?'})
    assert 'not contain enough' in no.json()['answer']

def test_numeric_claim_mismatch():
    assert numbers(chr(0x20ac)+'1,234.50 and '+chr(0x00a3)+'81.2') == [chr(0x20ac)+'1,234.50 ', chr(0x00a3)+'81.2']
    d=client.post('/api/documents',files={'file':('test.pdf',pdf_bytes(),'application/pdf')}).json()
    r=client.post('/api/claims/verify',json={'document_id':d['id'],'text':'Revenue reached 84 million dollars in 2024.'})
    assert r.status_code==200
    assert r.json()['status']=='contradicted'

def test_malformed_question_and_bad_page():
    assert client.post('/api/questions',json={'document_id':'missing','question':'x'}).status_code==422
    assert client.post('/api/questions',content='{bad json',headers={'content-type':'application/json'}).status_code==422
    assert client.get('/api/documents/missing/pages/1').status_code==404
