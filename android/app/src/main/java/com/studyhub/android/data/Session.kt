package com.studyhub.android.data

import android.content.Context
import org.json.JSONObject

/** Token + current user, kept in private preferences so a reinstall signs you out. */
class Session(context: Context) {

    private val prefs =
        context.applicationContext.getSharedPreferences("studyhub", Context.MODE_PRIVATE)

    var token: String? = prefs.getString(KEY_TOKEN, null)
        private set

    var user: User? = prefs.getString(KEY_USER, null)?.let(::decodeUser)
        private set

    val isSignedIn: Boolean get() = token != null

    fun save(token: String, user: User) {
        prefs.edit()
            .putString(KEY_TOKEN, token)
            .putString(KEY_USER, user.toJson().toString())
            .apply()
        this.token = token
        this.user = user
    }

    fun clear() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_USER).apply()
        token = null
        user = null
    }

    private fun decodeUser(raw: String): User? = try {
        User.fromJson(JSONObject(raw))
    } catch (error: Exception) {
        null
    }

    private companion object {
        const val KEY_TOKEN = "token"
        const val KEY_USER = "user"
    }
}
