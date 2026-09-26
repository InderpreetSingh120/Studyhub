package com.studyhub.android.data

import com.studyhub.android.BuildConfig
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

/** The server turned a request down; `message` is safe to show in the UI. */
class ApiException(val status: Int, message: String) : Exception(message)

data class DownloadedFile(val filename: String, val contentType: String, val bytes: ByteArray)

/** Blocking OkHttp calls, exposed as suspend functions so screens stay off the main thread. */
class Api(private val session: Session) {

    val baseUrl: String = BuildConfig.API_BASE_URL

    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    // --- auth ---------------------------------------------------------------

    suspend fun register(username: String, phone: String, password: String): TokenResponse =
        io {
            val payload = JSONObject()
                .put("username", username)
                .put("phone", phone)
                .put("password", password)
            Parsers.tokenResponse(post("auth/register", payload, auth = false))
        }

    suspend fun login(identifier: String, password: String): TokenResponse = io {
        val payload = JSONObject().put("identifier", identifier).put("password", password)
        Parsers.tokenResponse(post("auth/login", payload, auth = false))
    }

    suspend fun me(): User = io { Parsers.user(get("auth/me")) }

    // --- subjects -----------------------------------------------------------

    suspend fun subjects(): List<Subject> = io { Parsers.subjects(getArray("subjects")) }

    suspend fun createSubject(name: String, color: String?): Subject = io {
        val payload = JSONObject().put("name", name)
        if (color != null) payload.put("color", color)
        Parsers.subject(post("subjects", payload))
    }

    suspend fun updateSubject(id: Int, name: String, color: String?): Subject = io {
        val payload = JSONObject().put("name", name)
        if (color != null) payload.put("color", color) else payload.put("color", JSONObject.NULL)
        Parsers.subject(patch("subjects/$id", payload))
    }

    suspend fun deleteSubject(id: Int): Unit = io { delete("subjects/$id") }

    // --- notes --------------------------------------------------------------

    suspend fun notes(
        query: String? = null,
        subjectId: Int? = null,
        semester: Int? = null,
        branch: String? = null,
        kind: String? = null,
        mine: Boolean? = null,
        done: Boolean? = null,
        limit: Int = 200,
    ): List<Note> = io {
        val path = buildPath(
            "notes",
            mapOf(
                "q" to query?.takeIf { it.isNotBlank() },
                "subject_id" to subjectId?.toString(),
                "semester" to semester?.toString(),
                "branch" to branch?.takeIf { it.isNotBlank() },
                "kind" to kind,
                "mine" to mine?.toString(),
                "done" to done?.toString(),
                "limit" to limit.toString(),
            ),
        )
        Parsers.notes(getArray(path))
    }

    suspend fun note(id: Int): Note = io { Parsers.note(get("notes/$id")) }

    suspend fun createNote(
        title: String,
        body: String,
        subjectId: Int?,
        semester: Int,
        branch: String,
        kind: String,
        isDone: Boolean,
    ): Note = io {
        val payload = JSONObject()
            .put("title", title)
            .put("body", body)
            .put("semester", semester)
            .put("branch", branch)
            .put("kind", kind)
            .put("is_done", isDone)
        if (subjectId != null) payload.put("subject_id", subjectId) else payload.put("subject_id", JSONObject.NULL)
        Parsers.note(post("notes", payload))
    }

    suspend fun updateNote(
        id: Int,
        title: String,
        body: String,
        subjectId: Int?,
        semester: Int,
        branch: String,
        kind: String,
        isDone: Boolean,
    ): Note = io {
        val payload = JSONObject()
            .put("title", title)
            .put("body", body)
            .put("semester", semester)
            .put("branch", branch)
            .put("kind", kind)
            .put("is_done", isDone)
        if (subjectId != null) payload.put("subject_id", subjectId) else payload.put("subject_id", JSONObject.NULL)
        Parsers.note(patch("notes/$id", payload))
    }

    suspend fun deleteNote(id: Int): Unit = io { delete("notes/$id") }

    // --- attachments --------------------------------------------------------

    suspend fun attachments(noteId: Int): List<Attachment> =
        io { Parsers.attachments(getArray("notes/$noteId/attachments")) }

    suspend fun uploadAttachment(
        noteId: Int,
        filename: String,
        contentType: String,
        bytes: ByteArray,
    ): Attachment = io {
        val mediaType = contentType.toMediaTypeOrNullCompat()
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", filename, bytes.toRequestBody(mediaType))
            .build()
        Parsers.attachment(postBody("notes/$noteId/attachments", body))
    }

    suspend fun deleteAttachment(noteId: Int, attachmentId: Int): Unit =
        io { delete("notes/$noteId/attachments/$attachmentId") }

    suspend fun downloadAttachment(noteId: Int, attachmentId: Int): DownloadedFile = io {
        val response = executeForBytes(request("GET", "notes/$noteId/attachments/$attachmentId", null))
        val filename = response.headers["content-disposition"]
            ?.let { regexValue(it, "filename=\"?([^\";]+)\"?") }
            ?: "attachment"
        val contentType = response.headers["content-type"] ?: "application/octet-stream"
        DownloadedFile(filename, contentType, response.bytes)
    }

    // --- groups -------------------------------------------------------------

    suspend fun groups(): List<Group> = io { Parsers.groups(getArray("groups")) }

    suspend fun group(id: Int): Group = io { Parsers.group(get("groups/$id")) }

    suspend fun createGroup(name: String, description: String): Group = io {
        val payload = JSONObject().put("name", name).put("description", description)
        Parsers.group(post("groups", payload))
    }

    suspend fun joinGroup(inviteCode: String): Group = io {
        val payload = JSONObject().put("invite_code", inviteCode.trim().uppercase())
        Parsers.group(post("groups/join", payload))
    }

    suspend fun members(groupId: Int): List<GroupMember> =
        io { Parsers.members(getArray("groups/$groupId/members")) }

    suspend fun updateGroup(id: Int, name: String, description: String): Group = io {
        val payload = JSONObject().put("name", name).put("description", description)
        Parsers.group(patch("groups/$id", payload))
    }

    suspend fun leaveGroup(id: Int): Unit = io { postBody("groups/$id/leave", null) }

    suspend fun deleteGroup(id: Int): Unit = io { delete("groups/$id") }

    // --- chat ---------------------------------------------------------------

    suspend fun messages(groupId: Int, beforeId: Int? = null, limit: Int = 50): List<ChatMessage> =
        io {
            val path = buildPath(
                "groups/$groupId/messages",
                mapOf("before_id" to beforeId?.toString(), "limit" to limit.toString()),
            )
            Parsers.chatMessages(getArray(path))
        }

    suspend fun sendMessage(groupId: Int, body: String): ChatMessage = io {
        Parsers.chatMessage(post("groups/$groupId/messages", JSONObject().put("body", body)))
    }

    suspend fun globalMessages(beforeId: Int? = null, limit: Int = 50): List<ChatMessage> =
        io {
            val path = buildPath(
                "chat",
                mapOf("before_id" to beforeId?.toString(), "limit" to limit.toString()),
            )
            Parsers.chatMessages(getArray(path))
        }

    suspend fun postGlobalMessage(body: String): ChatMessage = io {
        Parsers.chatMessage(post("chat", JSONObject().put("body", body)))
    }

    // --- dashboard ----------------------------------------------------------

    suspend fun dashboard(): Dashboard = io { Parsers.dashboard(get("dashboard")) }

    // --- plumbing -----------------------------------------------------------

    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }

    private fun buildPath(path: String, query: Map<String, String?>): String {
        val params = query.filterValues { !it.isNullOrEmpty() }
        if (params.isEmpty()) return path
        val encoded = params.entries.joinToString("&") { (key, value) ->
            "${encode(key)}=${encode(value!!)}"
        }
        return "$path?$encoded"
    }

    private fun encode(value: String): String = URLEncoder.encode(value, "UTF-8")

    private fun get(path: String, auth: Boolean = true): JSONObject =
        JSONObject(execute(request("GET", path, null, auth)).orEmpty())

    private fun getArray(path: String, auth: Boolean = true): JSONArray =
        JSONArray(execute(request("GET", path, null, auth)).orEmpty())

    private fun post(path: String, payload: JSONObject?, auth: Boolean = true): JSONObject =
        JSONObject(
            execute(
                request(
                    "POST",
                    path,
                    (payload?.toString() ?: "").toRequestBody(jsonType),
                    auth,
                ),
            ).orEmpty(),
        )

    private fun postBody(path: String, body: RequestBody?): JSONObject =
        JSONObject(execute(request("POST", path, body)).orEmpty())

    private fun patch(path: String, payload: JSONObject): JSONObject =
        JSONObject(execute(request("PATCH", path, payload.toString().toRequestBody(jsonType))).orEmpty())

    private fun delete(path: String) {
        execute(request("DELETE", path, null))
    }

    private fun request(method: String, path: String, body: RequestBody?, auth: Boolean = true): Request {
        val builder = Request.Builder().url("$baseUrl/$path")
        if (auth) session.token?.let { builder.header("Authorization", "Bearer $it") }
        builder.method(method, body)
        return builder.build()
    }

    private class RawResponse(
        val status: Int,
        val body: String?,
        val headers: okhttp3.Headers,
    )

    private class RawBytes(val headers: okhttp3.Headers, val bytes: ByteArray)

    private fun execute(request: Request): String? =
        executeRaw(request).body

    private fun executeRaw(request: Request): RawResponse {
        try {
            http.newCall(request).execute().use { response ->
                val text = response.body?.string()
                if (!response.isSuccessful) throw ApiException(response.code, detailOf(text, response.code))
                return RawResponse(response.code, text, response.headers)
            }
        } catch (error: IOException) {
            throw ApiException(0, "Cannot reach the server")
        }
    }

    private fun executeForBytes(request: Request): RawBytes {
        try {
            http.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw ApiException(response.code, detailOf(response.body?.string(), response.code))
                }
                return RawBytes(response.headers, response.body?.bytes() ?: ByteArray(0))
            }
        } catch (error: IOException) {
            throw ApiException(0, "Cannot reach the server")
        }
    }

    private fun detailOf(text: String?, status: Int): String {
        if (text.isNullOrBlank()) return "Request failed ($status)"
        return try {
            val payload = JSONObject(text)
            when {
                !payload.has("detail") -> "Request failed ($status)"
                payload.isNull("detail") -> "Request failed ($status)"
                payload.opt("detail") is String -> payload.getString("detail")
                payload.opt("detail") is JSONArray -> {
                    val details = payload.getJSONArray("detail")
                    (0 until details.length()).joinToString(" · ") { index ->
                        val item = details.optJSONObject(index)
                        item?.optString("msg") ?: item.toString() ?: details.opt(index).toString()
                    }
                }
                else -> "Request failed ($status)"
            }
        } catch (error: Exception) {
            "Request failed ($status)"
        }
    }

    private fun regexValue(header: String, pattern: String): String? =
        Regex(pattern).find(header)?.groupValues?.getOrNull(1)

    private fun String?.orEmpty(): String = this ?: ""

    private fun String.toMediaTypeOrNullCompat() = try {
        toMediaType()
    } catch (error: Exception) {
        "application/octet-stream".toMediaType()
    }

    companion object {
        /** WebSocket twin of [baseUrl]; a null [groupId] means the everyone-chat. */
        fun socketUrl(baseUrl: String, groupId: Int?, token: String?): String {
            val wsBase = baseUrl.replaceFirst("http", "ws")
            val path = if (groupId == null) "/ws/global" else "/ws/groups/$groupId"
            val encoded = token?.let { "?token=${encode(it)}" } ?: ""
            return "$wsBase$path$encoded"
        }

        private fun encode(value: String): String = URLEncoder.encode(value, "UTF-8")
    }
}
