from __future__ import annotations
from typing import Dict, Any, List, Tuple, Iterable
from kubernetes import config as k8s_config, client as k8s_client
from kubernetes.client.exceptions import ApiException
import urllib3, time, json
from ..util import logging as log
urllib3.disable_warnings()

def load_kubeconfig(kubeconfig: str | None = None):
    if kubeconfig: k8s_config.load_kube_config(config_file=kubeconfig)
    else: k8s_config.load_kube_config()

def configure_from_credentials(credentials) -> k8s_client.Configuration:
    cfg = k8s_client.Configuration()
    cfg.host = credentials.host
    if credentials.token:
        cfg.api_key = {"authorization": credentials.token}
        cfg.api_key_prefix = {"authorization": "Bearer"}
        log.debug('using bearer token', host=credentials.host)
    elif credentials.username and credentials.password:
        import base64
        basic_auth = base64.b64encode(f"{credentials.username}:{credentials.password}".encode()).decode()
        cfg.api_key = {"authorization": f"Basic {basic_auth}"}
    if credentials.cert_file: cfg.cert_file = credentials.cert_file
    if credentials.key_file: cfg.key_file = credentials.key_file
    if credentials.ca_file: cfg.ssl_ca_cert = credentials.ca_file
    cfg.verify_ssl = credentials.verify_ssl
    if not credentials.verify_ssl: log.warn('ssl_verification_disabled', host=credentials.host)
    return cfg

STATIC_KIND_MAP: Dict[str, Tuple[str, str, bool]] = {
    'Deployment': ('apps/v1', 'deployments', True),
    'StatefulSet': ('apps/v1', 'statefulsets', True),
    'DaemonSet': ('apps/v1', 'daemonsets', True),
    'Job': ('batch/v1', 'jobs', True),
    'CronJob': ('batch/v1', 'cronjobs', True),
    'DeploymentConfig': ('apps.openshift.io/v1', 'deploymentconfigs', True),
    'BuildConfig': ('build.openshift.io/v1', 'buildconfigs', True),
    'ConfigMap': ('v1', 'configmaps', True),
    'Node': ('v1', 'nodes', False),
}

def _split_api_version(api_version: str) -> Tuple[str | None, str]:
    if '/' in api_version:
        group, version = api_version.split('/', 1)
        return group, version
    return None, api_version

def list_resources(api_client: k8s_client.ApiClient, api_version: str, plural: str, max_retries: int = 4, backoff_base: float = 0.5) -> Iterable[Dict[str, Any]]:
    group, version = _split_api_version(api_version)
    base = f"/api/{version}/{plural}" if group is None else f"/apis/{group}/{version}/{plural}"
    cont = None
    while True:
        query = f"?continue={cont}" if cont else ''
        url = base + query
        attempt = 0
        while True:
            try:
                resp = api_client.call_api(url, 'GET', response_type='object', _preload_content=False, auth_settings=['BearerToken'])
                payload = json.loads(resp[0].data)
                break
            except ApiException as e:
                status = getattr(e, 'status', None)
                if status in (403, 404):
                    log.warn('skipping kind due to access/availability', api_version=api_version, plural=plural, status=status)
                    return
                if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                    sleep_for = backoff_base * (2 ** attempt)
                    log.warn('transient error, retrying', api_version=api_version, plural=plural, status=status, attempt=attempt+1, sleep=sleep_for)
                    time.sleep(sleep_for); attempt += 1; continue
                log.error('failed listing resources', api_version=api_version, plural=plural, status=status, reason=str(e))
                return
            except Exception as e:
                if attempt < max_retries:
                    sleep_for = backoff_base * (2 ** attempt)
                    log.warn('generic error, retrying', api_version=api_version, plural=plural, attempt=attempt+1, sleep=sleep_for, error=str(e))
                    time.sleep(sleep_for); attempt += 1; continue
                log.error('unhandled error listing resources', api_version=api_version, plural=plural, error=str(e))
                return
        for item in payload.get('items', []):
            yield item
        cont = payload.get('metadata', {}).get('continue')
        if not cont:
            break

def resolve_kinds(include_kinds: List[str]) -> Dict[str, Tuple[str, str, bool]]:
    return {k: STATIC_KIND_MAP[k] for k in include_kinds if k in STATIC_KIND_MAP}

def list_namespaced_resources(api_client: k8s_client.ApiClient, api_version: str, plural: str, namespace: str, max_retries: int = 4, backoff_base: float = 0.5) -> Iterable[Dict[str, Any]]:
    """List resources restricted to a given namespace (namespace-scoped mode)."""
    group, version = _split_api_version(api_version)
    base = f"/api/{version}/namespaces/{namespace}/{plural}" if group is None else f"/apis/{group}/{version}/namespaces/{namespace}/{plural}"
    cont = None
    while True:
        query = f"?continue={cont}" if cont else ''
        url = base + query
        attempt = 0
        while True:
            try:
                resp = api_client.call_api(url, 'GET', response_type='object', _preload_content=False, auth_settings=['BearerToken'])
                payload = json.loads(resp[0].data)
                break
            except ApiException as e:
                status = getattr(e, 'status', None)
                if status in (403, 404):
                    log.warn('skipping namespace due to access/availability', api_version=api_version, plural=plural, namespace=namespace, status=status)
                    return
                if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                    sleep_for = backoff_base * (2 ** attempt)
                    log.warn('transient error, retrying', api_version=api_version, plural=plural, namespace=namespace, status=status, attempt=attempt+1, sleep=sleep_for)
                    time.sleep(sleep_for); attempt += 1; continue
                log.error('failed listing namespaced resources', api_version=api_version, plural=plural, namespace=namespace, status=status, reason=str(e))
                return
            except Exception as e:
                if attempt < max_retries:
                    sleep_for = backoff_base * (2 ** attempt)
                    log.warn('generic error, retrying', api_version=api_version, plural=plural, namespace=namespace, attempt=attempt+1, sleep=sleep_for, error=str(e))
                    time.sleep(sleep_for); attempt += 1; continue
                log.error('unhandled error listing namespaced resources', api_version=api_version, plural=plural, namespace=namespace, error=str(e))
                return
        for item in payload.get('items', []):
            yield item
        cont = payload.get('metadata', {}).get('continue')
        if not cont:
            break
