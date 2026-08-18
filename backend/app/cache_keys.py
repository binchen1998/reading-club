"""Redis key 统一前缀。分页用 idx SET 登记，禁止 SCAN。无 TTL。"""

PREFIX = "readingclub"

SQUARE_SNAPSHOT = f"{PREFIX}:square:snapshot"
SQUARE_DETAIL = f"{PREFIX}:square:detail:{{recording_id}}"
SQUARE_DETAIL_INDEX = f"{PREFIX}:idx:square_detail"
SQUARE_COMMENTS = f"{PREFIX}:square:comments:{{recording_id}}:p{{page}}:s{{page_size}}"
SQUARE_COMMENTS_INDEX = f"{PREFIX}:idx:square_comments:{{recording_id}}"
SQUARE_COMMENTS_ALL_INDEX = f"{PREFIX}:idx:square_comments:all"

NOTIF_UNREAD = f"{PREFIX}:notif:unread:{{username}}"
NOTIF_LIST = f"{PREFIX}:notif:list:{{username}}:p{{page}}:s{{page_size}}"
NOTIF_LIST_INDEX = f"{PREFIX}:idx:notif_list:{{username}}"

REPORT_HOME = f"{PREFIX}:report:home:{{username}}:{{date}}"
REPORT_MONTH = f"{PREFIX}:report:month:{{username}}:{{year}}:{{month}}:{{as_of}}"
REPORT_DAY = f"{PREFIX}:report:day:{{username}}:{{day}}"
REPORT_INDEX = f"{PREFIX}:idx:report:{{username}}"

USER_ME = f"{PREFIX}:user:me:{{username}}"
PROFILE = f"{PREFIX}:profile:{{username}}:p{{page}}:s{{page_size}}"
PROFILE_INDEX = f"{PREFIX}:idx:profile:{{username}}"
PROFILE_WALL = f"{PREFIX}:profile:wall:{{username}}:p{{page}}:s{{page_size}}"
PROFILE_WALL_INDEX = f"{PREFIX}:idx:profile_wall:{{username}}"
PROFILE_WALL_ALL_INDEX = f"{PREFIX}:idx:profile_wall:all"
FOLLOWERS = f"{PREFIX}:followers:{{username}}:p{{page}}:s{{page_size}}"
FOLLOWERS_INDEX = f"{PREFIX}:idx:followers:{{username}}"
FOLLOWING = f"{PREFIX}:following:{{username}}:p{{page}}:s{{page_size}}"
FOLLOWING_INDEX = f"{PREFIX}:idx:following:{{username}}"

WRONG_CURRENT = f"{PREFIX}:wrong:current:{{username}}"
WRONG_HISTORY = f"{PREFIX}:wrong:history:{{username}}"
WRONG_INDEX = f"{PREFIX}:idx:wrong:{{username}}"
