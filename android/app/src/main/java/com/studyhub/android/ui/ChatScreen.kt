package com.studyhub.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.studyhub.android.AppModel
import com.studyhub.android.data.ChatMessage
import com.studyhub.android.data.ChatSocket
import kotlinx.coroutines.launch

private const val HISTORY_PAGE = 50

/** The room every signed-in user shares; groups keep their own private rooms. */
@Composable
fun ChatScreen(
    model: AppModel,
    onSignedOut: () -> Unit,
) {
    var messages by remember { mutableStateOf<List<ChatMessage>?>(null) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var socketError by remember { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf("connecting") }
    var draft by remember { mutableStateOf("") }
    var attempt by remember { mutableStateOf(0) }
    var chatSocket by remember { mutableStateOf<ChatSocket?>(null) }
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()

    fun append(incoming: ChatMessage) {
        val current = messages ?: return
        messages = if (current.any { it.id == incoming.id }) current else current + incoming
    }

    LaunchedEffect(Unit) {
        try {
            error = null
            messages = model.api.globalMessages(limit = HISTORY_PAGE)
        } catch (cause: Throwable) {
            error = cause
        }
    }

    DisposableEffect(attempt) {
        val chat = ChatSocket(
            api = model.api,
            token = model.session.token,
            groupId = null,
            listener = object : ChatSocket.Listener {
                override fun onConnected() {
                    scope.launch { status = "online" }
                }

                override fun onMessage(message: ChatMessage) {
                    scope.launch { append(message) }
                }

                override fun onError(detail: String) {
                    scope.launch { socketError = detail }
                }

                override fun onClosed(code: Int, reason: String) {
                    scope.launch {
                        status = "offline"
                        if (code == 4401) {
                            model.signOut()
                            onSignedOut()
                        }
                    }
                }
            },
        )
        status = "connecting"
        socketError = null
        chat.connect()
        chatSocket = chat
        onDispose {
            chat.close()
            chatSocket = null
        }
    }

    LaunchedEffect(messages?.size) {
        val size = messages?.size ?: 0
        if (size > 0) listState.animateScrollToItem(size - 1)
    }

    fun send() {
        val body = draft.trim()
        if (body.isEmpty()) return
        draft = ""
        socketError = null
        if (chatSocket?.send(body) == true) return
        scope.launch {
            try {
                append(model.api.postGlobalMessage(body))
            } catch (cause: Throwable) {
                socketError = messageOf(cause)
            }
        }
    }

    fun loadOlder() {
        val oldest = messages?.firstOrNull() ?: return
        scope.launch {
            try {
                val older = model.api.globalMessages(beforeId = oldest.id, limit = HISTORY_PAGE)
                messages = older + (messages ?: emptyList())
            } catch (cause: Throwable) {
                error = cause
            }
        }
    }

    val currentMessages = messages
    Column(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "Everyone's chat", style = MaterialTheme.typography.headlineSmall)
                Text(
                    text = "One room for the whole campus",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            StatusDot(status = status)
        }

        ErrorNote(error)
        socketError?.let { detail ->
            Text(
                text = detail,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(vertical = 4.dp),
            )
        }

        when {
            currentMessages == null -> Loading("Opening the chat…")
            currentMessages.isEmpty() -> EmptyState(
                title = "No messages yet",
                message = "Say hello — everyone signed in will see it live.",
            )
            else -> LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 8.dp),
            ) {
                if (currentMessages.size >= HISTORY_PAGE) {
                    item {
                        TextButton(onClick = ::loadOlder) { Text("Load earlier messages") }
                    }
                }
                items(currentMessages, key = { it.id }) { message ->
                    ChatBubble(message = message, mine = message.senderId == model.user?.id)
                }
            }
        }

        if (status == "offline") {
            OutlinedButton(
                onClick = { attempt += 1 },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Reconnect") }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                placeholder = { Text("Write a message to everyone…") },
                modifier = Modifier.weight(1f),
                singleLine = true,
            )
            Button(onClick = ::send, enabled = draft.isNotBlank()) { Text("Send") }
        }
    }
}
