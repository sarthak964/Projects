import io
from types import SimpleNamespace

from PIL import Image

from app.models import LedgerEntry, PhotoReview, ReviewerProfile
from app.services.verification_state import VerificationOutput

CHECKLIST = ['AC working', 'Fire extinguisher']


def image_bytes(fmt='JPEG'):
    output = io.BytesIO()
    Image.new('RGB', (12, 12), 'grey').save(output, format=fmt)
    return output.getvalue()


class Inspection:
    """Exercise the real HTTP, persistence, image and graph layers with mocked LLMs."""

    def __init__(self, client, headers, store, monkeypatch):
        self.client, self.headers, self.store, self.patch = client, headers, store, monkeypatch
        self.job_id = None
        self.report_id = None

    def call(self, method, path, uid=4, **kwargs):
        response = self.client.request(method, path, headers=self.headers(uid), **kwargs)
        assert response.status_code == 200, (method, path, response.status_code, response.text)
        return response.json()

    def create(self):
        from app.routers import job
        self.patch.setattr(job, 'geocode_address', lambda address: {'lat': 12.97, 'lng': 77.59})
        result = self.call('POST', '/jobs/', json={'address': 'Test inspection property', 'checklist': CHECKLIST})
        self.job_id = result['id']
        return result

    def accept(self):
        return self.call('POST', f'/jobs/{self.job_id}/accept', uid=5)

    def visit(self):
        return self.call('POST', f'/jobs/{self.job_id}/visit', uid=5)

    def upload(self, item='AC working', uid=5, data=None, fmt='JPEG'):
        return self.call('POST', f'/jobs/{self.job_id}/photos', uid=uid,
                         data={'checklist_item': item},
                         files={'file': ('evidence.jpg', data if data is not None else image_bytes(fmt), 'image/jpeg')})

    def submit(self, notes='AC working. No fire extinguisher found.'):
        result = self.call('POST', '/reports/', uid=5, json={'job_id': self.job_id, 'notes': notes})
        self.report_id = result['id']
        return result

    def ai_output(self, items, photo_check='no_photo', addressed=True):
        from app.services import verification_nodes as nodes
        nodes.structured_llm.invoke.side_effect = None
        nodes.structured_llm.invoke.return_value = VerificationOutput(results=[{
            'item': item, 'addressed': addressed,
            'passed': addressed and item == 'AC working',
            'photo_check': photo_check,
            'photo_observation': 'Mock image observation' if photo_check != 'no_photo' else 'no photos',
            'confidence': .9, 'reasoning': 'Deterministic test result',
        } for item in items])
        nodes.llm.invoke.side_effect = None
        nodes.llm.invoke.return_value = SimpleNamespace(content='Mock inspection summary')

    def verify(self, addressed=True):
        from app.routers import report
        from app.services.verification_graph import verification_graph
        self.patch.setattr(report, 'verification_graph', verification_graph)
        self.ai_output(CHECKLIST, addressed=addressed)
        return self.call('POST', f'/reports/{self.report_id}/verify', uid=5)

    def start(self):
        self.create()
        self.accept()
        self.visit()
        for item in CHECKLIST:
            self.upload(item)
        self.submit()
        self.verify()
        return self

    def reject(self, verdict='supports', items=None):
        from app.routers import photo_review
        from app.services.photo_review_ai import check_photos
        items = items or ['AC working']
        quote = self.call('GET', f'/jobs/{self.job_id}/photo-review/fee-quote', params=[('items', item) for item in items])
        self.patch.setattr(photo_review, 'check_photos', check_photos)
        self.ai_output(list(dict.fromkeys(items)), photo_check=verdict)
        return self.call('POST', f'/jobs/{self.job_id}/photo-review/reject', json={'items': items, 'reason': 'Test rejected evidence', 'confirm_fee': quote['fee']})

    def reupload(self):
        self.upload()
        return self.call('POST', f'/jobs/{self.job_id}/photo-review/reupload-complete', uid=5)

    def dispute_ai(self, fee=75):
        return self.call('POST', f'/jobs/{self.job_id}/photo-review/dispute-ai-result', json={'reason': 'Please review the evidence', 'confirm_fee': fee})

    def decide(self, decision):
        return self.call('POST', f'/admin/photo-reviews/{self.job_id}/decide', uid=1, json={'decision': decision, 'notes': 'Deterministic human decision'})

    def profile(self):
        with self.store() as db:
            return db.query(ReviewerProfile).filter_by(user_id=5).one()

    def review(self):
        with self.store() as db:
            return db.query(PhotoReview).filter_by(job_id=self.job_id).first()

    def balances(self, renter, reviewer, platform, escrow=0):
        observed = {'renter:4': 0, 'reviewer:5': 0, 'platform': 0, 'escrow': 0}
        with self.store() as db:
            for row in db.query(LedgerEntry).filter_by(job_id=self.job_id).all():
                observed[row.debit_account] -= row.amount_paise
                observed[row.credit_account] += row.amount_paise
        assert observed == {'renter:4': renter, 'reviewer:5': reviewer, 'platform': platform, 'escrow': escrow}
        assert self.call('GET', '/admin/ledger/summary', uid=1)['balanced'] is True
