package com.studyhub.android.data

import org.json.JSONArray
import org.json.JSONObject

/** One data class per object in docs/api.md, with org.json parsers. */

const val KIND_NOTES = "notes"
const val KIND_PRACTICAL = "practical"
const val KIND_MST = "mst"
const val KIND_FINAL = "final"

val NOTE_KINDS = listOf(KIND_NOTES, KIND_PRACTICAL, KIND_MST, KIND_FINAL)

val KIND_LABELS = mapOf(
    KIND_NOTES to "Notes",
    KIND_PRACTICAL to "Practical",
    KIND_MST to "MST",
    KIND_FINAL to "Finals",
)

val SEMESTERS = (1..8).toList()

val BRANCHES = listOf("CSE", "IT", "ECE", "EEE", "MECH", "CIVIL")

data class User(
    val id: Int,
    val username: String,
    val phone: String,
    val role: String,
    val createdAt: String,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("id", id)
        .put("username", username)
        .put("phone", phone)
        .put("role", role)
        .put("created_at", createdAt)

    companion object {
        fun fromJson(json: JSONObject) = Parsers.user(json)
    }
}

data class TokenResponse(val accessToken: String, val user: User)

data class Subject(
    val id: Int,
    val name: String,
    val color: String?,
    val createdBy: Int?,
    val createdAt: String,
)

data class Note(
    val id: Int,
    val title: String,
    val body: String,
    val subjectId: Int?,
    val semester: Int,
    val branch: String,
    val kind: String,
    val kindLabel: String,
    val isDone: Boolean,
    val authorId: Int,
    val author: String,
    val attachmentCount: Int,
    val createdAt: String,
    val updatedAt: String,
)

data class Attachment(
    val id: Int,
    val filename: String,
    val contentType: String,
    val sizeBytes: Long,
    val summary: String?,
    val summaryStatus: String,
    val createdAt: String,
)

data class Group(
    val id: Int,
    val name: String,
    val description: String,
    val inviteCode: String,
    val createdAt: String,
    val memberCount: Int,
    val myRole: String,
)

data class GroupMember(
    val userId: Int,
    val username: String,
    val role: String,
    val joinedAt: String,
)

/** Shared by group rooms and the everyone-chat (`groupId` is 0 for the latter). */
data class ChatMessage(
    val id: Int,
    val groupId: Int,
    val senderId: Int,
    val sender: String,
    val body: String,
    val createdAt: String,
)

data class SubjectCount(
    val subjectId: Int,
    val name: String,
    val color: String?,
    val count: Int,
)

data class LabelCount(val key: String, val label: String, val count: Int)

data class DashboardNote(
    val id: Int,
    val title: String,
    val author: String,
    val subjectId: Int?,
    val semester: Int,
    val branch: String,
    val kind: String,
    val isDone: Boolean,
    val updatedAt: String,
)

data class MessagePreview(val sender: String, val body: String, val createdAt: String)

data class DashboardGroup(
    val id: Int,
    val name: String,
    val memberCount: Int,
    val lastMessage: MessagePreview?,
)

data class TrendPoint(val date: String, val count: Int)

data class Dashboard(
    val totalNotes: Int,
    val doneNotes: Int,
    val withoutSubject: Int,
    val bySubject: List<SubjectCount>,
    val byKind: List<LabelCount>,
    val byBranch: List<LabelCount>,
    val bySemester: List<LabelCount>,
    val recentNotes: List<DashboardNote>,
    val groups: List<DashboardGroup>,
    val trend: List<TrendPoint>,
)

internal fun <T> JSONArray.mapJson(transform: (JSONObject) -> T): List<T> {
    val out = ArrayList<T>(length())
    for (index in 0 until length()) out.add(transform(getJSONObject(index)))
    return out
}

internal fun JSONObject.stringOrNull(key: String): String? =
    if (isNull(key)) null else optString(key).ifEmpty { null }

internal fun JSONObject.intOrNull(key: String): Int? = if (isNull(key)) null else getInt(key)

object Parsers {

    fun user(json: JSONObject) = User(
        id = json.getInt("id"),
        username = json.getString("username"),
        phone = json.optString("phone", ""),
        role = json.optString("role", "user"),
        createdAt = json.optString("created_at", ""),
    )

    fun tokenResponse(json: JSONObject) = TokenResponse(
        accessToken = json.getString("access_token"),
        user = user(json.getJSONObject("user")),
    )

    fun subject(json: JSONObject) = Subject(
        id = json.getInt("id"),
        name = json.getString("name"),
        color = json.stringOrNull("color"),
        createdBy = json.intOrNull("created_by"),
        createdAt = json.optString("created_at", ""),
    )

    fun note(json: JSONObject) = Note(
        id = json.getInt("id"),
        title = json.getString("title"),
        body = json.optString("body", ""),
        subjectId = json.intOrNull("subject_id"),
        semester = json.optInt("semester", 1),
        branch = json.optString("branch", ""),
        kind = json.optString("kind", KIND_NOTES),
        kindLabel = json.optString("kind_label", KIND_LABELS[KIND_NOTES].orEmpty()),
        isDone = json.optBoolean("is_done", false),
        authorId = json.optInt("author_id", 0),
        author = json.optString("author", ""),
        attachmentCount = json.optInt("attachment_count", 0),
        createdAt = json.optString("created_at", ""),
        updatedAt = json.optString("updated_at", ""),
    )

    fun attachment(json: JSONObject) = Attachment(
        id = json.getInt("id"),
        filename = json.getString("filename"),
        contentType = json.optString("content_type", "application/octet-stream"),
        sizeBytes = json.optLong("size_bytes", 0L),
        summary = json.stringOrNull("summary"),
        summaryStatus = json.optString("summary_status", "pending"),
        createdAt = json.optString("created_at", ""),
    )

    fun group(json: JSONObject) = Group(
        id = json.getInt("id"),
        name = json.getString("name"),
        description = json.optString("description", ""),
        inviteCode = json.optString("invite_code", ""),
        createdAt = json.optString("created_at", ""),
        memberCount = json.optInt("member_count", 0),
        myRole = json.optString("my_role", "member"),
    )

    fun member(json: JSONObject) = GroupMember(
        userId = json.getInt("user_id"),
        username = json.getString("username"),
        role = json.optString("role", "member"),
        joinedAt = json.optString("joined_at", ""),
    )

    fun chatMessage(json: JSONObject) = ChatMessage(
        id = json.getInt("id"),
        groupId = json.optInt("group_id", 0),
        senderId = json.optInt("sender_id", 0),
        sender = json.optString("sender", ""),
        body = json.getString("body"),
        createdAt = json.optString("created_at", ""),
    )

    fun dashboard(json: JSONObject): Dashboard {
        val notes = json.getJSONObject("notes")
        val bySubject = notes.getJSONArray("by_subject").mapJson { item ->
            SubjectCount(
                subjectId = item.getInt("subject_id"),
                name = item.getString("name"),
                color = item.stringOrNull("color"),
                count = item.getInt("count"),
            )
        }
        fun labelCounts(key: String): List<LabelCount> =
            notes.optJSONArray(key)?.mapJson { item ->
                LabelCount(
                    key = item.getString("key"),
                    label = item.optString("label", item.getString("key")),
                    count = item.getInt("count"),
                )
            } ?: emptyList()

        val recent = json.getJSONArray("recent_notes").mapJson { item ->
            DashboardNote(
                id = item.getInt("id"),
                title = item.getString("title"),
                author = item.optString("author", ""),
                subjectId = item.intOrNull("subject_id"),
                semester = item.optInt("semester", 1),
                branch = item.optString("branch", ""),
                kind = item.optString("kind", KIND_NOTES),
                isDone = item.optBoolean("is_done", false),
                updatedAt = item.optString("updated_at", ""),
            )
        }
        val groups = json.getJSONArray("groups").mapJson { item ->
            val preview = item.optJSONObject("last_message")
            DashboardGroup(
                id = item.getInt("id"),
                name = item.getString("name"),
                memberCount = item.optInt("member_count", 0),
                lastMessage = preview?.let {
                    MessagePreview(
                        sender = it.optString("sender", ""),
                        body = it.optString("body", ""),
                        createdAt = it.optString("created_at", ""),
                    )
                },
            )
        }
        val trend = json.getJSONArray("trend").mapJson { item ->
            TrendPoint(
                date = item.getString("date"),
                count = item.getInt("count"),
            )
        }
        return Dashboard(
            totalNotes = notes.optInt("total", 0),
            doneNotes = notes.optInt("done", 0),
            withoutSubject = notes.optInt("without_subject", 0),
            bySubject = bySubject,
            byKind = labelCounts("by_kind"),
            byBranch = labelCounts("by_branch"),
            bySemester = labelCounts("by_semester"),
            recentNotes = recent,
            groups = groups,
            trend = trend,
        )
    }

    fun subjects(json: JSONArray) = mapJson(json, ::subject)
    fun notes(json: JSONArray) = mapJson(json, ::note)
    fun attachments(json: JSONArray) = mapJson(json, ::attachment)
    fun groups(json: JSONArray) = mapJson(json, ::group)
    fun members(json: JSONArray) = mapJson(json, ::member)
    fun chatMessages(json: JSONArray) = mapJson(json, ::chatMessage)

    private fun <T> mapJson(array: JSONArray, transform: (JSONObject) -> T): List<T> =
        array.mapJson(transform)
}
