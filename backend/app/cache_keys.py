"""Redis key 统一前缀。分页用 idx SET 登记，禁止 SCAN。无 TTL。"""

PREFIX = "readingclub"

SQUARE_SNAPSHOT = f"{PREFIX}:square:snapshot"
SQUARE_DETAIL = f"{PREFIX}:square:detail:{{recording_id}}"
SQUARE_DETAIL_INDEX = f"{PREFIX}:idx:square_detail"

REPORT_HOME = f"{PREFIX}:report:home:{{username}}:{{date}}"
REPORT_MONTH = f"{PREFIX}:report:month:{{username}}:{{year}}:{{month}}:{{as_of}}"
REPORT_DAY = f"{PREFIX}:report:day:{{username}}:{{day}}"
REPORT_INDEX = f"{PREFIX}:idx:report:{{username}}"

USER_ME = f"{PREFIX}:user:me:{{username}}"
PROFILE = f"{PREFIX}:profile:{{username}}:p{{page}}:s{{page_size}}"
PROFILE_INDEX = f"{PREFIX}:idx:profile:{{username}}"

WRONG_CURRENT = f"{PREFIX}:wrong:current:{{username}}"
WRONG_HISTORY = f"{PREFIX}:wrong:history:{{username}}"
WRONG_INDEX = f"{PREFIX}:idx:wrong:{{username}}"
