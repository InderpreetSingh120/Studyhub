package com.studyhub.android.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import com.studyhub.android.data.KIND_LABELS
import com.studyhub.android.data.KIND_NOTES
import com.studyhub.android.data.NOTE_KINDS
import com.studyhub.android.data.SEMESTERS
import com.studyhub.android.data.Subject
import kotlinx.coroutines.launch

@Composable
fun NoteEditorScreen(
    model: AppModel,
    noteId: Int,
    onDone: () -> Unit,
) {
    val isNew = noteId <= 0
    val context = LocalContext.current
    var title by remember { mutableStateOf("") }
    var body by remember { mutableStateOf("") }
    var subjectId by remember { mutableStateOf<Int?>(null) }
    var semester by remember { mutableStateOf(1) }
    var branch by remember { mutableStateOf("CSE") }
    var kind by remember { mutableStateOf(KIND_NOTES) }
    var isDone by remember { mutableStateOf(false) }
    var subjects by remember { mutableStateOf<List<Subject>>(emptyList()) }
    var attachments by remember { mutableStateOf<List<Attachment>?>(null) }
    var loading by remember { mutableStateOf(!isNew) }
    var busy by remember { mutableStateOf(false) }
    var transferring by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var showDelete by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun refreshAttachments() {
        attachments = model.api.attachments(noteId)
    }

    LaunchedEffect(Unit) {
        try {
            subjects = model.api.subjects()
        } catch (cause: Throwable) {
            error = cause
        }
        if (!isNew) {
            try {
                val note = model.api.note(noteId)
                title = note.title
                body = note.body
                subjectId = note.subjectId
                semester = note.semester
                branch = note.branch
                kind = note.kind
                isDone = note.isDone
            } catch (cause: Throwable) {
                error = cause
            } finally {
                loading = false
            }
            try {
                refreshAttachments()
            } catch (cause: Throwable) {
                error = cause
            }
        }
    }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            transferring = true
            error = null
            try {
                val resolver = context.contentResolver
                val type = resolver.getType(uri) ?: "application/octet-stream"
                val name = queryName(context, uri) ?: "attachment"
                val bytes = resolver.openInputStream(uri)?.use { stream -> stream.readBytes() }
                    ?: ByteArray(0)
                model.api.uploadAttachment(noteId, name, type, bytes)
                refreshAttachments()
            } catch (cause: Throwable) {
                error = cause
            } finally {
                transferring = false
            }
        }
    }

    fun viewAttachment(attachment: Attachment) {
        openAttachment(
            context = context,
            api = model.api,
            noteId = noteId,
            attachment = attachment,
            scope = scope,
            onBusy = { transferring = it },
            onError = { error = it },
        )
    }

    fun save() {
        scope.launch {
            busy = true
            error = null
            try {
                if (isNew) {
                    model.api.createNote(
                        title.trim(), body, subjectId, semester, branch, kind, isDone,
                    )
                } else {
                    model.api.updateNote(
                        noteId, title.trim(), body, subjectId, semester, branch, kind, isDone,
                    )
                }
                onDone()
            } catch (cause: Throwable) {
                error = cause
            } finally {
                busy = false
            }
        }
    }

    if (showDelete) {
        AlertDialog(
            onDismissRequest = { showDelete = false },
            title = { Text("Delete note?") },
            text = { Text("\"$title\" will be removed for good.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            try {
                                model.api.deleteNote(noteId)
                                onDone()
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
        loading -> Loading("Opening the note…")
        error != null && title.isEmpty() && !isNew -> Column(modifier = Modifier.padding(16.dp)) {
            ErrorNote(error)
            OutlinedButton(onClick = onDone) { Text("Back") }
        }
        else -> Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = if (isNew) "New note" else "Edit note",
                    style = MaterialTheme.typography.headlineSmall,
                    modifier = Modifier.weight(1f),
                )
                if (!isNew) {
                    TextButton(onClick = { showDelete = true }) { Text("Delete") }
                }
            }

            StudyHubTextField(value = title, onValueChange = { title = it }, label = "Title")
            OutlinedTextField(
                value = body,
                onValueChange = { body = it },
                label = { Text("Body") },
                modifier = Modifier.fillMaxWidth().height(200.dp),
            )

            Text(text = "Subject", style = MaterialTheme.typography.titleSmall)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = subjectId == null,
                    onClick = { subjectId = null },
                    label = { Text("None") },
                )
                subjects.forEach { subject ->
                    FilterChip(
                        selected = subjectId == subject.id,
                        onClick = { subjectId = subject.id },
                        label = { Text(subject.name) },
                    )
                }
            }

            Text(text = "Semester", style = MaterialTheme.typography.titleSmall)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SEMESTERS.forEach { value ->
                    FilterChip(
                        selected = semester == value,
                        onClick = { semester = value },
                        label = { Text("Sem $value") },
                    )
                }
            }

            StudyHubTextField(value = branch, onValueChange = { branch = it }, label = "Branch")

            Text(text = "Type", style = MaterialTheme.typography.titleSmall)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                NOTE_KINDS.forEach { value ->
                    FilterChip(
                        selected = kind == value,
                        onClick = { kind = value },
                        label = { Text(KIND_LABELS.getValue(value)) },
                    )
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "Done",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyLarge,
                )
                Switch(checked = isDone, onCheckedChange = { isDone = it })
            }

            if (!isNew) {
                Text(text = "Attachments", style = MaterialTheme.typography.titleSmall)
                val current = attachments.orEmpty()
                if (current.isEmpty()) {
                    Text(
                        text = "No files attached",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                current.forEach { attachment ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
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
                                onClick = { viewAttachment(attachment) },
                            ) { Text("Open") }
                            TextButton(
                                enabled = !transferring,
                                onClick = {
                                    scope.launch {
                                        try {
                                            model.api.deleteAttachment(noteId, attachment.id)
                                            refreshAttachments()
                                        } catch (cause: Throwable) {
                                            error = cause
                                        }
                                    }
                                },
                            ) { Text("Delete") }
                        }
                    }
                }
                OutlinedButton(
                    enabled = !transferring,
                    onClick = { picker.launch(arrayOf("*/*")) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (transferring) "Working…" else "Attach a file")
                }
            }

            ErrorNote(error)

            Button(
                onClick = ::save,
                enabled = title.isNotBlank() && branch.isNotBlank() && !busy,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (busy) "Saving…" else "Save note")
            }
        }
    }
}
