from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class ReconciliationInput(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    shift_a_start: datetime
    shift_a_end: datetime
    shift_b_start: datetime
    shift_b_end: datetime

    @model_validator(mode='after')
    def _check_windows(self):
        if not (self.shift_a_start < self.shift_a_end):
            raise ValueError('A班时段开始必须早于结束')
        if not (self.shift_b_start < self.shift_b_end):
            raise ValueError('B班时段开始必须早于结束')
        overlap = max(self.shift_a_start, self.shift_b_start) < min(self.shift_a_end, self.shift_b_end)
        if overlap:
            raise ValueError('两个班次时段不能重叠')
        return self

class ReconciliationPairQuery(BaseModel):
    node_name: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
