"""
Fetch AWS Pricing Calculator estimate data directly from the CloudFront API.

No browser automation needed — the estimate JSON is publicly accessible at:
  https://d3knqfixx3sbls.cloudfront.net/{estimate_id}

This endpoint is discovered by observing network traffic when the calculator
page loads the estimate. It is a public, unauthenticated CDN endpoint.
"""
import re
import requests

# CloudFront CDN that hosts estimate JSON files
_CF_BASE = "https://d3knqfixx3sbls.cloudfront.net"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://calculator.aws/",
    "Origin":  "https://calculator.aws",
}


# ── Public API ────────────────────────────────────────────────────────────────

def extract_urls(cell_value: str) -> list[str]:
    return re.findall(r'https://calculator\.aws/[^\s"\'<>]+', str(cell_value))


def extract_estimate_id(url: str) -> str | None:
    m = re.search(r'[?&]id=([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None


def fetch_estimate_instances(url: str) -> dict[str, int]:
    """
    Fetch estimate from AWS Calculator CloudFront API and return
    {instance_type: total_count} aggregated across all groups/environments.

    Raises RuntimeError on network or parsing failure.
    """
    est_id = extract_estimate_id(url)
    if not est_id:
        raise RuntimeError(f"Não foi possível extrair o estimate ID de: {url}")

    api_url = f"{_CF_BASE}/{est_id}"
    print(f"  [api] GET {api_url}")

    try:
        resp = requests.get(api_url, headers=_HEADERS, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Erro de rede ao buscar estimativa {est_id}: {exc}")

    if resp.status_code != 200:
        raise RuntimeError(
            f"API retornou {resp.status_code} para estimativa {est_id}"
        )

    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Resposta não é JSON válido: {exc}")

    instances: dict[str, int] = {}
    _collect_services(data, instances)

    print(f"  [api] Instâncias encontradas: {dict(instances)}")
    return instances


# ── Internal helpers ──────────────────────────────────────────────────────────

_NON_COMPUTE = re.compile(r"^ultrawarm", re.IGNORECASE)

def _clean_instance_name(inst: str) -> str:
    """Remove vendor prefixes (db., cache.) and the .search suffix from instance names."""
    for prefix in ("db.", "cache."):
        if inst.startswith(prefix):
            inst = inst[len(prefix):]
            break
    if inst.endswith(".search"):
        inst = inst[: -len(".search")]
    return inst


def _is_valid_instance(name: str) -> bool:
    """Return False for storage tiers or other non-compute identifiers."""
    return not _NON_COMPUTE.match(name)


def classify_processor(instance_type: str) -> str:
    """
    Classify the processor architecture of an AWS instance type.
    Returns 'Intel', 'AMD', or 'Graviton'.

    Rules follow AWS naming convention:
      - Suffix 'g' after generation number → Graviton (e.g. m8g, r6g, t4g)
      - Suffix 'a' after generation number → AMD    (e.g. m7a, c6a, r5a)
      - Suffix 'i' or no suffix           → Intel   (e.g. m7i, c8i, t3)
      - Mac instances (Apple Silicon ARM)  → Graviton
    """
    family = instance_type.split(".")[0].lower()

    # Mac instances — Apple Silicon (ARM-based)
    if family.startswith("mac"):
        return "Graviton"

    # Standard pattern: [series_letters][generation_digits][suffix_letters]
    m = re.match(r"^([a-z]+)(\d+)([a-z]*)$", family)
    if not m:
        return "Intel"   # safe default for unrecognised formats

    _series, _gen, suffix = m.groups()

    if not suffix:
        return "Intel"   # older instances (T2, T3, M5, etc.) are Intel

    first = suffix[0]
    if first == "g":
        return "Graviton"
    if first == "a":
        return "AMD"
    return "Intel"  # 'i', 'd', 'n', 'z', 'b', 'e', … all Intel


def _collect_services(node: dict, acc: dict[str, int]) -> None:
    """Walk the estimate tree and accumulate instance counts."""
    if not isinstance(node, dict):
        return

    for svc in node.get("services", {}).values():
        _parse_service(svc, acc)

    for group in node.get("groups", {}).values():
        _collect_services(group, acc)


def _parse_service(svc: dict, acc: dict[str, int]) -> None:
    """Extract (instance_type, count) from one service entry."""
    code  = svc.get("serviceCode", "")
    comps = svc.get("calculationComponents", {})
    if not comps:
        return

    # ── EC2 (serviceCode: ec2Enhancement) ────────────────────────────────────
    if "ec2Enhancement" in code or "instanceType" in comps:
        inst = _deep(comps, "instanceType", "value")
        cnt  = _deep(comps, "workload", "value", "data")
        if inst and cnt:
            try:
                count = int(cnt)
                if count > 0:
                    key = _clean_instance_name(inst.lower())
                    acc[key] = acc.get(key, 0) + count
                return
            except (ValueError, TypeError):
                pass

    # ── RDS / OpenSearch: all columnFormIPM* keys ────────────────────────────
    # RDS uses columnFormIPM; OpenSearch uses columnFormIPM, columnFormIPM_1,
    # columnFormIPM_2 … for UltraWarm, data nodes, and master nodes respectively.
    ipm_keys = sorted(k for k in comps if k.startswith("columnFormIPM"))
    if ipm_keys:
        for key in ipm_keys:
            ipm = _deep(comps, key, "value")
            if not isinstance(ipm, list):
                continue
            for row in ipm:
                if not isinstance(row, dict):
                    continue
                inst = _deep(row, "Instance Type", "value")
                if not inst:
                    continue
                # Find the count field: any key whose name starts with
                # "Number of Nodes" covers RDS, OpenSearch data, and master nodes.
                cnt = None
                for field in row:
                    if field.startswith("Number of Nodes"):
                        cnt = _deep(row, field, "value")
                        break
                # Fallback for RDS-style "Nodes" key
                if cnt is None:
                    cnt = _deep(row, "Nodes", "value")
                try:
                    count = int(cnt or 0)
                except (ValueError, TypeError):
                    count = 0
                if count == 0:
                    continue  # skip zero-count entries (UltraWarm with 0 nodes, etc.)
                clean = _clean_instance_name(inst.lower())
                if not _is_valid_instance(clean):
                    continue  # skip non-compute tiers (ultrawarm, etc.)
                acc[clean] = acc.get(clean, 0) + count
        return

    # ── Generic fallback: scan all component values for AWS instance patterns ─
    _generic_scan(comps, acc)


def _generic_scan(comps: dict, acc: dict[str, int]) -> None:
    """Last-resort regex scan of all component values."""
    _INST_RE = re.compile(
        r'\b((?:db\.)?[a-z][0-9]+[a-z]*\.(?:nano|micro|small|medium|large|[0-9]+xlarge|metal))\b',
        re.IGNORECASE,
    )
    text = str(comps)
    for match in _INST_RE.findall(text):
        inst = match.lower()
        acc[inst] = acc.get(inst, 0) + 1


def _deep(obj, *keys):
    """Safe nested dict access."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj
