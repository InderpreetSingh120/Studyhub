package com.studyhub.android.data

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File
import java.io.IOException

/**
 * Saves a downloaded attachment into the public Downloads folder and returns a
 * message for the UI. API 29+ goes through MediaStore; older devices write the
 * file directly (the manifest grants WRITE_EXTERNAL_STORAGE up to API 28).
 */
fun saveToDownloads(context: Context, filename: String, contentType: String, bytes: ByteArray): String {
    val safeName = filename.replace(Regex("[/\\\\:*?\"<>|]"), "_").ifBlank { "attachment" }

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, safeName)
            put(MediaStore.Downloads.MIME_TYPE, contentType)
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = context.contentResolver.insert(
            MediaStore.Downloads.EXTERNAL_CONTENT_URI,
            values,
        ) ?: throw IOException("Could not create a Downloads entry")
        context.contentResolver.openOutputStream(uri)?.use { stream -> stream.write(bytes) }
            ?: throw IOException("Could not write $safeName")
        values.clear()
        values.put(MediaStore.Downloads.IS_PENDING, 0)
        context.contentResolver.update(uri, values, null, null)
        return "Saved to Downloads as $safeName"
    }

    @Suppress("DEPRECATION")
    val directory = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
    if (!directory.exists()) directory.mkdirs()
    var target = File(directory, safeName)
    if (target.exists()) {
        val base = safeName.substringBeforeLast('.')
        val extension = safeName.substringAfterLast('.', "")
        var index = 1
        while (target.exists()) {
            target = File(directory, if (extension.isEmpty()) "$base ($index)" else "$base ($index).$extension")
            index += 1
        }
    }
    target.writeBytes(bytes)
    MediaScannerConnection.scanFile(context, arrayOf(target.absolutePath), arrayOf(contentType), null)
    return "Saved to Downloads as ${target.name}"
}
