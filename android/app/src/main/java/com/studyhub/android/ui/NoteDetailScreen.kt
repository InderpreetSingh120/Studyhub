package com.studyhub.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.studyhub.android.AppModel
import com.studyhub.android.data.Attachment
import com.studyhub.android.data.Note
import com.studyhub.android.data.Subject
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun NoteDetailScreen(
    model: AppModel,
    noteId: Int,
    onBack: () -> Unit,
    onEdit: () -> Unit,
    onDeleted: () -> Unit,
) {
    val context = LocalContext.current
    var note by remember { mutableStateOf<Note?>(null) }
    var subjects by remember { mutableStateOf<List<Subject>>(emptyList()) }
    var files by remember { mutableStateOf<List<Attachment>?>(null) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var transferring by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    var showDelete by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun load() {
        scope.launch {
            try {
                error = null
                note = model.api.note(noteId)
                files = model.api.attachments(noteId)
            } catch (cause: Throwable) {
                error = cause
            }
        }
    }

    LaunchedEffect(Unit) {
        try {
            subjects = model.api.subjects()
        } catch (_: Throwable) {
            subjects = emptyList()
        }
        load()
    }

    // The summary job runs on the server after an upload; poll while it works.
    LaunchedEffect(files?.any { it.summaryStatus == "pending" }) {
        while (files?.any { it.summaryStatus == "pending" } == true) {
            delay(3000)
            try {
                files = model.api.attachments(noteId)
            } catch (_: Throwable) {
                delay(3000)
            }
        }
    }

    val current = note
    val owner = current != null &&
        (model.user?.id == current.authorId || model.user?.role == "admin")

    if (showDelete && current != null) {
        AlertDialog(
            onDismissRequest = { showDelete = false },
            title = { Text("Delete note?") },
            text = { Text("\"${current.title}\" and its files are removed for everyone.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            try {
                                model.api.deleteNote(noteId)
                                onDeleted()
                            } catch (cause: Throwable) {
                                error = cause
                                showDelete = false
                            }
                        }
                    },
                ) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { showDelete = false }) { Text("Cancel") }
            },
        )
    }

    when {
        current == null && error != null -> Column(modifier = Modifier.padding(16.dp)) {
            ErrorNote(error)
            OutlinedButton(onClick = onBack) { Text("Back") }
        }
        current == null -> Loading("Opening the note…")
        else -> Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(onClick = onBack) { Text("Back") }
                Column(modifier = Modifier.weight(1f).padding(horizontal = 8.dp)) {
                    Text(text = current.title, style = MaterialTheme.typography.headlineSmall)
                    Text(
                        text = "by ${current.author}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (owner) {
                    TextButton(onClick = onEdit) { Text("Edit") }
                    TextButton(onClick = { showDelete = true }) { Text("Delete") }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                InfoChip(current.kindLabel, primary = true)
                InfoChip("Semester ${current.semester}")
                InfoChip(current.branch)
                subjects.firstOrNull { it.id == current.subjectId }
                    ?.let { InfoChip(it.name, primary = true) }
                if (current.isDone) InfoChip("Completed") else InfoChip("Open")
            }

            Text(
                text = "Updated ${shortDate(current.updatedAt)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Notes", style = MaterialTheme.typography.titleMedium)
                    if (current.body.isBlank()) {
                        Text(
                            text = "No written notes — open the files below.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        Text(text = current.body, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }

            val currentFiles = files
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("AI summary", style = MaterialTheme.typography.titleMedium)
                    when {
                        currentFiles == null -> Text("…", style = MaterialTheme.typography.bodyMedium)
                        currentFiles.isEmpty() -> Text(
                            text = "Upload a PDF and a short summary of it is generated automatically.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        else -> currentFiles.forEach { file ->
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(
                                    text = file.filename,
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                                Text(
                                    text = when (file.summaryStatus) {
                                        "ready" -> file.summary.orEmpty().ifBlank { "No summary text." }
                                        "pending" -> "Writing a summary for this file…"
                                        "skipped" -> "Summary skipped — AI summaries are turned off on this server."
                                        else -> "The summary could not be generated for this file."
                                    },
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (file.summaryStatus == "ready") {
                                        MaterialTheme.colorScheme.onSurface
                                    } else {
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                    },
                                )
                            }
                        }
                    }
                }
            }

            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Files", style = MaterialTheme.typography.titleMedium)
                    val currentList = currentFiles.orEmpty()
                    if (currentList.isEmpty()) {
                        Text(
                            text = "No files on this note yet.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    currentList.forEach { attachment ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(attachment.filename, style = MaterialTheme.typography.bodyMedium)
                                Text(
                                    text = formatSize(attachment.sizeBytes),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            TextButton(
                                enabled = !transferring,
                                onClick = {
                                    openAttachment(
                                        context = context,
                                        api = model.api,
                                        noteId = noteId,
                                        attachment = attachment,
                                        scope = scope,
                                        onBusy = { transferring = it },
                                        onError = { error = it },
                                    )
                                },
                            ) { Text("Open") }
                            TextButton(
                                enabled = !transferring,
                                onClick = {
                                    downloadAttachment(
                                        context = context,
                                        api = model.api,
                                        noteId = noteId,
                                        attachment = attachment,
                                        scope = scope,
                                        onBusy = { transferring = it },
                                        onMessage = { notice = it },
                                        onError = { error = it },
                                    )
                                },
                            ) { Text("Download") }
                            if (owner) {
                                TextButton(
                                    enabled = !transferring,
                                    onClick = {
                                        scope.launch {
                                            try {
                                                model.api.deleteAttachment(noteId, attachment.id)
                                                files = model.api.attachments(noteId)
                                            } catch (cause: Throwable) {
                                                error = cause
                                            }
                                        }
                                    },
                                ) { Text("Remove") }
                            }
                        }
                    }
                }
            }

            ErrorNote(error)
            notice?.let { message ->
                Text(
                    text = message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun InfoChip(text: String, primary: Boolean = false) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = if (primary) MaterialTheme.colorScheme.primary
        else MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(end = 8.dp),
    )
}
