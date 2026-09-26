package com.studyhub.android.data

import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject

/** Thin wrapper over OkHttp's WebSocket with the frames documented in docs/api.md.
 *  A null [groupId] connects to the room everyone shares. */
class ChatSocket(
    private val api: Api,
    private val token: String?,
    private val groupId: Int?,
    private val listener: Listener,
) {

    interface Listener {
        fun onConnected()
        fun onMessage(message: ChatMessage)
        fun onError(detail: String)
        fun onClosed(code: Int, reason: String)
    }

    private val http = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private var socket: WebSocket? = null

    fun connect() {
        val request = Request.Builder()
            .url(Api.socketUrl(api.baseUrl, groupId, token))
            .build()
        socket = http.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onMessage(webSocket: WebSocket, text: String) {
                    val frame = try {
                        JSONObject(text)
                    } catch (error: Exception) {
                        return
                    }
                    when (frame.optString("type")) {
                        "connected" -> listener.onConnected()
                        "message" -> listener.onMessage(Parsers.chatMessage(frame.getJSONObject("message")))
                        "error" -> listener.onError(frame.optString("detail", "Chat error"))
                    }
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    webSocket.close(code, reason)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    listener.onClosed(code, reason)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    listener.onClosed(1006, t.message ?: "connection lost")
                }
            },
        )
    }

    fun send(body: String): Boolean {
        val current = socket ?: return false
        return current.send(
            JSONObject().put("type", "message").put("body", body).toString(),
        )
    }

    fun isOpen(): Boolean = socket != null

    fun close() {
        socket?.close(1000, "bye")
        socket = null
        http.dispatcher.executorService.shutdown()
    }
}
