package com.studyhub.android.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.core.content.FileProvider
import com.studyhub.android.data.Api
import com.studyhub.android.data.Attachment
import com.studyhub.android.data.saveToDownloads
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/** Fetches an attachment and hands it to the system viewer through the FileProvider. */
internal fun openAttachment(
    context: Context,
    api: Api,
    noteId: Int,
    attachment: Attachment,
    scope: CoroutineScope,
    onBusy: (Boolean) -> Unit,
    onError: (Throwable) -> Unit,
) {
    scope.launch {
        onBusy(true)
        try {
            val file = api.downloadAttachment(noteId, attachment.id)
            val directory = File(context.cacheDir, "attachments").apply { mkdirs() }
            val target = File(directory, file.filename.replace(Regex("[/\\\\]"), "_"))
            target.writeBytes(file.bytes)
            val uri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                target,
            )
            val view = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, file.contentType)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(view, "Open ${file.filename}"))
        } catch (cause: Throwable) {
            onError(cause)
        } finally {
            onBusy(false)
        }
    }
}

/** Fetches an attachment and copies it into the public Downloads folder. */
internal fun downloadAttachment(
    context: Context,
    api: Api,
    noteId: Int,
    attachment: Attachment,
    scope: CoroutineScope,
    onBusy: (Boolean) -> Unit,
    onMessage: (String) -> Unit,
    onError: (Throwable) -> Unit,
) {
    scope.launch {
        onBusy(true)
        try {
            val file = api.downloadAttachment(noteId, attachment.id)
            onMessage(saveToDownloads(context, file.filename, file.contentType, file.bytes))
        } catch (cause: Throwable) {
            onError(cause)
        } finally {
            onBusy(false)
        }
    }
}

internal fun queryName(context: Context, uri: Uri): String? =
    context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (index >= 0 && cursor.moveToFirst()) cursor.getString(index) else null
    }

internal fun formatSize(bytes: Long): String = when {
    bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0)
    bytes >= 1_024 -> "%.1f KB".format(bytes / 1_024.0)
    else -> "$bytes B"
}
