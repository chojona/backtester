from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib,json
from ..sessions import SessionCalendar,NY


@dataclass(frozen=True)
class CoverageAssessment:
    state: str                 # PROVIDER_AVAILABLE or UNKNOWN
    evidence: str


class ProviderCoverage:
    def __init__(self, start, end, conditions, completed=False):
        self.start,self.end,self.completed=start,end,completed
        self.days={row['date']:row['condition'] for row in conditions}

    def at(self, timestamp, duration=timedelta(minutes=1)):
        if not self.completed or timestamp < self.start or timestamp+duration > self.end:
            return CoverageAssessment('UNKNOWN','Request incomplete or interval outside successfully downloaded range')
        first=timestamp.astimezone(timezone.utc).date().isoformat()
        last=(timestamp+duration-timedelta(microseconds=1)).astimezone(timezone.utc).date().isoformat()
        if all(self.days.get(day)=='available' for day in {first,last}):
            return CoverageAssessment('PROVIDER_AVAILABLE','Complete untruncated stream + provider daily condition=available; minute completeness is inferred, not independently proven')
        return CoverageAssessment('UNKNOWN','Provider day is degraded, pending, missing, or has no condition metadata')


class DatedSessionCalendar(SessionCalendar):
    """A bounded explicit schedule; never derives exchange closures from empty data."""
    def __init__(self, document, source_path=None):
        allowed={'version','product','timezone','dates','source_urls','reviewed_at','status','source_files','notes'}
        if set(document)-allowed:
            raise ValueError('Unknown dated calendar fields')
        if document.get('product')!='NQ' or document.get('timezone')!='America/New_York':
            raise ValueError('Calendar must explicitly cover NQ in America/New_York')
        if not document.get('source_urls') or not document.get('version') or not document.get('dates'):
            raise ValueError('Calendar requires sources, version and explicit dates')
        self.document=document
        self.source_path=source_path
        super().__init__(template='equity',breaks=[],overrides=document['dates'],
                         source='Dated NQ calendar '+document['version']+'; '+document.get('status','unverified'))

    @classmethod
    def from_file(cls,path):
        document=json.loads(Path(path).read_text())
        for item in document.get('source_files',[]):
            source=(Path(path).parent/item['path']).resolve()
            if not source.is_relative_to(Path(path).parent.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('Calendar source file hash mismatch')
        return cls(document,str(Path(path).resolve()))

    def classify(self,timestamp):
        if timestamp.tzinfo is None:
            raise ValueError('Timezone-aware timestamp required')
        local=timestamp.astimezone(NY)
        day=local.date()+timedelta(days=1) if local.hour>=18 else local.date()
        # Weekends are closed by the explicit exchange convention, but weekday exceptions must exist.
        if day.weekday()<5 and day.isoformat() not in self.document['dates']:
            raise ValueError('Dated calendar does not cover trading date '+day.isoformat())
        return super().classify(timestamp)

    def verify_range(self,start,end):
        probe=start
        while probe<end:
            self.classify(probe)
            probe+=timedelta(minutes=1)

    def provenance(self):
        payload=json.dumps(self.document,sort_keys=True,separators=(',',':')).encode()
        return dict(document=self.document,document_sha256=hashlib.sha256(payload).hexdigest(),source_path=self.source_path)
