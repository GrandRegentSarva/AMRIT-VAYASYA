from __future__ import annotations

import pytest

from core.frontend_extractor import extract_http_calls


ANGULAR_SAMPLE = """
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class BeneficiaryService {
  constructor(private http: HttpClient) {}

  getBeneficiary(id: string) {
    return this.http.get<Beneficiary>('/api/beneficiary/' + id);
  }

  registerBeneficiary(data: any) {
    return this.http.post('/api/beneficiary/register', data);
  }

  updateBeneficiary(id: string, data: any) {
    return this.http.put(`/api/beneficiary/${id}`, data);
  }
}
"""

AXIOS_SAMPLE = """
const fetchPatient = () => axios.get('/api/patient/123');
const createPatient = () => axios.post('/api/patient', payload);
"""

FETCH_SAMPLE = """
const response = await fetch('/api/auth/login', {
  method: 'POST',
  body: JSON.stringify(credentials),
});
const data = await fetch('/api/beneficiary');
"""

JAVA_SAMPLE = """
public class FhirClient {
    public PatientDto getPatient(String id) {
        return restTemplate.getForObject("/api/fhir/patient/" + id, PatientDto.class);
    }
}
"""


def test_angular_http_get():
    calls = extract_http_calls(ANGULAR_SAMPLE, 'typescript')
    methods = {c['method'] for c in calls}
    paths = {c['path'] for c in calls}
    assert 'GET' in methods
    assert any('/api/beneficiary' in p for p in paths)


def test_angular_http_post():
    calls = extract_http_calls(ANGULAR_SAMPLE, 'typescript')
    post_calls = [c for c in calls if c['method'] == 'POST']
    assert len(post_calls) >= 1
    assert any('register' in c['path'] for c in post_calls)


def test_axios_extraction():
    calls = extract_http_calls(AXIOS_SAMPLE, 'typescript')
    assert any(c['method'] == 'GET' and 'patient' in c['path'] for c in calls)
    assert any(c['method'] == 'POST' and 'patient' in c['path'] for c in calls)


def test_fetch_extraction():
    calls = extract_http_calls(FETCH_SAMPLE, 'javascript')
    assert any(c['path'] == '/api/auth/login' for c in calls)
    assert any(c['path'] == '/api/beneficiary' for c in calls)


def test_java_rest_template():
    calls = extract_http_calls(JAVA_SAMPLE, 'java')
    assert any('fhir' in c['path'] for c in calls)


def test_empty_text():
    calls = extract_http_calls('', 'typescript')
    assert calls == []


def test_no_api_paths_ignored():
    # External URLs should not be included
    text = "this.http.get('https://external.com/api/data')"
    calls = extract_http_calls(text, 'typescript')
    assert len(calls) == 0


def test_deduplication():
    text = """
    this.http.get('/api/beneficiary');
    this.http.get('/api/beneficiary');
    """
    calls = extract_http_calls(text, 'typescript')
    assert len([c for c in calls if c['path'] == '/api/beneficiary']) == 1
