package com.wardrobe.ootd

import android.content.ContentResolver
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrl
import java.io.IOException
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit

@Serializable
data class Item(
    val id: Int,
    val name: String,
    val category: String,
    val color: String? = null,
    val image_url: String,
    val stored_name: String = "",
)

@Serializable
data class Outfit(
    val id: Int,
    val name: String,
    val created_at: String,
    val items: List<OutfitPiece> = emptyList(),
)

@Serializable
data class OutfitPiece(
    val item_id: Int? = null,
    val name: String,
    val available: Boolean = true,
    val image_url: String? = null,
)

@Serializable
data class WearEvent(
    val id: Int,
    val worn_on: String? = null,
    val outfit_id: Int? = null,
    val created_at: String,
    val items: List<OutfitPiece> = emptyList(),
    val already_recorded: Boolean = false,
)

@Serializable
data class WearStats(
    val counts: Map<String, Int> = emptyMap(),
    val last_worn: Map<String, String> = emptyMap(),
)

@Serializable
data class SuggestedPiece(val id: Int, val name: String, val category: String, val image_url: String? = null)

@Serializable
data class PaletteColor(val hex: String, val name: String? = null, val share: Double = 0.0)

@Serializable
data class PaletteWrap(val palette: List<PaletteColor> = emptyList())

@Serializable
data class Suggestion(
    val items: List<SuggestedPiece>,
    val score: Double,
    val verdict: String,
    val notes: List<String> = emptyList(),
    val palette: PaletteWrap? = null,
)

@Serializable
data class Suggestions(val suggestions: List<Suggestion> = emptyList(), val guidance: String? = null)

@Serializable
private data class ApiDetail(val detail: String)

@Serializable
private data class CreateOutfitBody(val name: String, val item_ids: List<Int>)

@Serializable
private data class RecordWearBody(val item_ids: List<Int>, val outfit_id: Int?, val worn_on: String?)

@Serializable
private data class DeletedOutfitResponse(val deleted: Int)

@Serializable
private data class LoginBody(val email: String, val password: String)

@Serializable
private data class SignupBody(val email: String, val password: String, val display_name: String?)

@Serializable
private data class LoginResponse(val ok: Boolean = false, val token: String? = null)

@Serializable
data class UploadCandidate(
    val name: String,
    val category: String,
    val stored_name: String,
    val color: String? = null,
    val bytes: Long,
    val confidence: Double? = null,
    val image_url: String,
)

@Serializable
data class UploadResponse(
    val upload_id: Int,
    val original_stored_name: String,
    val duplicate_of_existing: Boolean = false,
    val notice: String? = null,
    val candidates: List<UploadCandidate> = emptyList(),
)

@Serializable
private data class SaveItemBody(
    val name: String,
    val category: String,
    val stored_name: String,
    val color: String? = null,
    val upload_id: Int,
)

@Serializable
private data class ManualItemBody(val name: String, val category: String, val is_manual: Int)

@Serializable
private data class UpdateItemBody(val name: String, val category: String)

@Serializable
private data class DeletedItemResponse(val deleted: Int)

@Serializable
data class UserProfile(
    val id: Int,
    val email: String,
    val display_name: String? = null,
    val is_admin: Boolean = false,
    val created_at: String = "",
)

@Serializable
private data class UpdateProfileBody(val display_name: String)

/** Shown to the user as-is, so the text has to make sense on a phone screen. */
class ApiError(message: String) : Exception(message)

/** The session is gone; the caller must send the user back to sign in. */
class Unauthorized : Exception("Session expired")

class Api(private val store: Store) {

    private val json = Json { ignoreUnknownKeys = true }

    var lastServerAnswered by mutableStateOf<String?>(null)
        private set

    private val probeClient = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(2, TimeUnit.SECONDS)
        .build()
    private val serverLock = Any()
    private var cachedBase: String? = null
    private var cacheExpiresAt = 0L

    /** Prefer the laptop while its lightweight health endpoint responds. */
    private fun base(): String {
        // Image models are built during composition. Use the last IO-resolved
        // address there; never perform the health probe on the main thread.
        if (Looper.myLooper() == Looper.getMainLooper()) {
            return synchronized(serverLock) { cachedBase ?: store.baseUrl }
        }
        return synchronized(serverLock) {
            val now = System.nanoTime()
            if (cachedBase != null && now < cacheExpiresAt) return@synchronized cachedBase!!
            val laptop = store.baseUrl
            val laptopResponds = try {
                val request = Request.Builder().url("${laptop.trimEnd('/')}/healthz").get().build()
                probeClient.newCall(request).execute().use { it.isSuccessful }
            } catch (_: IOException) {
                false
            } catch (_: IllegalArgumentException) {
                false
            }
            cachedBase = if (laptopResponds || store.cloudUrl.isBlank()) laptop else store.cloudUrl
            cacheExpiresAt = now + TimeUnit.SECONDS.toNanos(30)
            cachedBase!!
        }
    }

    fun forgetServer() = synchronized(serverLock) {
        cachedBase = null
        cacheExpiresAt = 0L
    }

    private fun unreachable(laptopMessage: String): ApiError = ApiError(
        if (store.cloudUrl.isNotBlank()) "Cannot reach your laptop or the cloud server." else laptopMessage
    )

    /**
     * Shared with Coil, so item images carry the token too. The server returns
     * 404 for an unauthenticated image request, which would otherwise show up
     * as every tile being blank rather than as a sign-in problem.
     */
    val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val token = store.token
            val request = if (token == null) {
                chain.request()
            } else {
                chain.request().newBuilder()
                    .header("Authorization", "Bearer $token")
                    .build()
            }
            val response = chain.proceed(request)
            val answeredUrl = response.request.url
            val laptopUrl = runCatching { store.baseUrl.toHttpUrl() }.getOrNull()
            lastServerAnswered = if (laptopUrl != null && answeredUrl.host == laptopUrl.host && answeredUrl.port == laptopUrl.port) {
                "Laptop"
            } else {
                "Cloud server"
            }
            response
        }
        .build()

    private val uploadClient = client.newBuilder()
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    /** Returns the session token, which the caller is responsible for storing. */
    fun login(email: String, password: String): String {
        val body = json.encodeToString(LoginBody(email, password))
            .toRequestBody("application/json".toMediaType())

        // client=mobile is required: without it the server replies with an
        // httponly cookie and no token, which a native app cannot use.
        val request = Request.Builder()
            .url("${base()}/api/auth/login?client=mobile")
            .post(body)
            .build()

        try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                when {
                    response.code == 401 -> throw ApiError("Wrong email or password")
                    response.code == 429 -> throw ApiError("Too many attempts. Wait a minute.")
                    !response.isSuccessful -> throw ApiError("Sign-in failed (${response.code})")
                }
                return json.decodeFromString<LoginResponse>(text).token
                    ?: throw ApiError("The laptop sent no token. Is it running the current version?")
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Cannot reach the laptop at ${store.baseUrl}. Same Wi-Fi, and is it awake?")
        }
    }

    /** Creates an account. Signup does not create a session; the caller signs in separately. */
    fun signup(email: String, password: String, displayName: String?) {
        val body = json.encodeToString(SignupBody(email, password, displayName))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${base()}/api/auth/signup")
            .post(body)
            .build()

        try {
            client.newCall(request).execute().use { response ->
                when (response.code) {
                    400 -> throw ApiError("This email is already registered. Sign in instead.")
                    422 -> throw ApiError("Check that your email is valid and your password has at least 10 characters.")
                    429 -> throw ApiError("Too many attempts. Wait a minute.")
                }
                if (!response.isSuccessful) throw ApiError("Account creation failed (${response.code})")
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Cannot reach the laptop at ${store.baseUrl}. Same Wi-Fi, and is it awake?")
        }
    }

    fun currentUser(): UserProfile {
        val request = Request.Builder().url("${base()}/api/auth/me").get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not load your account (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop at ${store.baseUrl}.")
        }
    }

    fun updateDisplayName(displayName: String): UserProfile {
        val body = json.encodeToString(UpdateProfileBody(displayName))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${base()}/api/auth/me")
            .patch(body)
            .build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (response.code == 422) throw ApiError("Display name must be 1 to 60 characters after trimming.")
                if (!response.isSuccessful) throw ApiError("Could not update your display name (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while updating your display name.")
        }
    }

    fun items(category: String = "all", query: String = ""): List<Item> {
        val url = "${base()}/api/items".toHttpUrl().newBuilder()
            .addQueryParameter("category", category)
            .addQueryParameter("q", query)
            .addQueryParameter("sort", "newest")
            .build()
        val request = Request.Builder().url(url).build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not load your closet (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop at ${store.baseUrl}.")
        }
    }

    /** Returns null when the item has already been removed or is not yours. */
    fun updateItem(id: Int, name: String, category: String): Item? {
        val body = json.encodeToString(UpdateItemBody(name, category))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${base()}/api/items/$id")
            .patch(body)
            .build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (response.code == 404) return null
                if (!response.isSuccessful) throw ApiError("Could not update this piece (${response.code})")
                return json.decodeFromString<Item>(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while updating this piece.")
        }
    }

    /** Returns false when the item has already been removed or is not yours. */
    fun deleteItem(id: Int): Boolean {
        val request = Request.Builder().url("${base()}/api/items/$id").delete().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (response.code == 404) return false
                if (!response.isSuccessful) throw ApiError("Could not delete this piece (${response.code})")
                json.decodeFromString<DeletedItemResponse>(response.body?.string().orEmpty())
                return true
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while deleting this piece.")
        }
    }

    fun outfits(): List<Outfit> {
        val request = Request.Builder().url("${base()}/api/outfits").get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not load your outfits (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop at ${store.baseUrl}.")
        }
    }

    fun suggestions(limit: Int = 5): Suggestions {
        val url = "${base()}/api/outfits/recommendations".toHttpUrl().newBuilder()
            .addQueryParameter("limit", limit.coerceIn(1, 10).toString()).build()
        val request = Request.Builder().url(url).get().build()
        try {
            client.newCall(request).execute().use { response ->
                val body = response.body?.string().orEmpty()
                if (response.code == 401) throw Unauthorized()
                if (response.code == 400) {
                    val detail = runCatching { json.decodeFromString<ApiDetail>(body).detail }.getOrNull()
                    throw ApiError(detail ?: "Could not generate recommendations (${response.code})")
                }
                if (!response.isSuccessful) throw ApiError("Could not load recommendations (${response.code})")
                return json.decodeFromString(body)
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop at ${store.baseUrl}.")
        }
    }

    fun createOutfit(name: String, itemIds: List<Int>): Outfit {
        val body = json.encodeToString(CreateOutfitBody(name, itemIds)).toRequestBody("application/json".toMediaType())
        val request = Request.Builder().url("${base()}/api/outfits").post(body).build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not save this outfit (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while saving this outfit.")
        }
    }

    fun outfit(id: Int): Outfit {
        val request = Request.Builder().url("${base()}/api/outfits/$id").get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (response.code == 404) throw ApiError("This outfit is no longer available.")
                if (!response.isSuccessful) throw ApiError("Could not load this outfit (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while loading this outfit.")
        }
    }

    fun deleteOutfit(id: Int): Boolean {
        val request = Request.Builder().url("${base()}/api/outfits/$id").delete().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (response.code == 404) return false
                if (!response.isSuccessful) throw ApiError("Could not delete this outfit (${response.code})")
                json.decodeFromString<DeletedOutfitResponse>(response.body?.string().orEmpty())
                return true
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while deleting this outfit.")
        }
    }

    fun recordWear(itemIds: List<Int>, outfitId: Int?, wornOn: String?): WearEvent {
        val body = json.encodeToString(RecordWearBody(itemIds, outfitId, wornOn)).toRequestBody("application/json".toMediaType())
        val request = Request.Builder().url("${base()}/api/wears").post(body).build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not record this wear (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while recording this wear.")
        }
    }

    fun wears(limit: Int = 50): List<WearEvent> {
        val url = "${base()}/api/wears".toHttpUrl().newBuilder()
            .addQueryParameter("limit", limit.toString()).build()
        val request = Request.Builder().url(url).get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not load wear history (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop at ${store.baseUrl}.")
        }
    }

    fun wearStats(): WearStats {
        val request = Request.Builder().url("${base()}/api/wears/stats").get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not load wear stats (${response.code})")
                return json.decodeFromString(response.body?.string().orEmpty())
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop at ${store.baseUrl}.")
        }
    }

    fun deleteWear(id: Int): Boolean {
        val request = Request.Builder().url("${base()}/api/wears/$id").delete().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 401) throw Unauthorized()
                if (response.code == 404) return false
                if (!response.isSuccessful) throw ApiError("Could not delete this wear (${response.code})")
                json.decodeFromString<DeletedOutfitResponse>(response.body?.string().orEmpty())
                return true
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while deleting this wear.")
        }
    }

    fun upload(uri: Uri, resolver: ContentResolver): UploadResponse {
        val bytes = try {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            // decodeStream always returns null while inJustDecodeBounds is set, so the
            // null check belongs on the stream. Testing the decode result made every
            // single upload throw "Could not open that photo".
            val boundsStream = resolver.openInputStream(uri)
                ?: throw ApiError("Could not open that photo")
            boundsStream.use { BitmapFactory.decodeStream(it, null, bounds) }
            val width = bounds.outWidth
            val height = bounds.outHeight
            if (width <= 0 || height <= 0) throw ApiError("Could not read that photo")
            val orientation = resolver.openInputStream(uri)?.use { exif ->
                ExifInterface(exif).getAttributeInt(
                    ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL
                )
            } ?: ExifInterface.ORIENTATION_NORMAL
            val sample = ((maxOf(width, height) / 2048f).toInt()).coerceAtLeast(1)
            val bitmap = resolver.openInputStream(uri)?.use { image ->
                BitmapFactory.decodeStream(image, null, BitmapFactory.Options().apply { inSampleSize = sample })
            } ?: throw ApiError("Could not open that photo")
            val scaled = if (maxOf(bitmap.width, bitmap.height) > 2048) {
                val ratio = 2048f / maxOf(bitmap.width, bitmap.height)
                Bitmap.createScaledBitmap(bitmap, (bitmap.width * ratio).toInt(), (bitmap.height * ratio).toInt(), true)
            } else bitmap
            // A phone records a portrait shot as landscape pixels plus an EXIF
            // rotation tag. Bitmap.compress drops that tag, so without this the
            // laptop receives a sideways photo, fails to find a person in it,
            // and silently runs the flat-lay path on a worn outfit.
            val upright = applyOrientation(scaled, orientation)
            ByteArrayOutputStream().use { output ->
                upright.compress(Bitmap.CompressFormat.JPEG, 88, output)
                if (upright !== scaled) upright.recycle()
                if (scaled !== bitmap) scaled.recycle()
                bitmap.recycle()
                output.toByteArray()
            }
        } catch (e: ApiError) {
            throw e
        } catch (e: Exception) {
            throw ApiError("Could not prepare that photo")
        }
        if (bytes.size > 10 * 1024 * 1024) throw ApiError("That photo is still over 10 MB. Choose a smaller image.")
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", "closet-photo.jpg", bytes.toRequestBody("image/jpeg".toMediaType()))
            .build()
        val request = Request.Builder().url("${base()}/api/uploads").post(body).build()
        try {
            uploadClient.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (response.code == 401) throw Unauthorized()
                when {
                    response.code == 429 -> throw ApiError("Upload limit reached: 5 photos per minute. Please wait a minute and try again.")
                    response.code == 413 -> throw ApiError("That photo is too large. Choose a smaller image.")
                    !response.isSuccessful -> throw ApiError("Photo upload failed (${response.code})")
                }
                return json.decodeFromString<UploadResponse>(text)
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Upload timed out or lost the laptop. Keep the app open and try again.")
        }
    }

    fun saveCandidate(candidate: UploadCandidate, uploadId: Int): Item {
        val body = json.encodeToString(
            SaveItemBody(candidate.name, candidate.category, candidate.stored_name, candidate.color, uploadId)
        ).toRequestBody("application/json".toMediaType())
        val request = Request.Builder().url("${base()}/api/items").post(body).build()
        try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not save ${candidate.name} (${response.code})")
                return json.decodeFromString<Item>(text)
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while saving ${candidate.name}.")
        }
    }

    fun createManualItem(name: String, category: String): Item {
        val body = json.encodeToString(ManualItemBody(name, category, 1))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder().url("${base()}/api/items").post(body).build()
        try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (response.code == 401) throw Unauthorized()
                if (!response.isSuccessful) throw ApiError("Could not save this piece (${response.code})")
                return json.decodeFromString<Item>(text)
            }
        } catch (e: IOException) {
            forgetServer()
            throw unreachable("Lost the laptop while saving this piece.")
        }
    }

    /** Clears the token locally even when the laptop is unreachable. */
    fun logout() {
        try {
            val request = Request.Builder()
                .url("${base()}/api/auth/logout")
                .post(ByteArray(0).toRequestBody())
                .build()
            client.newCall(request).execute().close()
        } catch (e: IOException) {
            // Signing out of a sleeping laptop must still sign you out here.
        } finally {
            store.token = null
        }
    }

    private fun applyOrientation(bitmap: Bitmap, orientation: Int): Bitmap {
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            else -> return bitmap
        }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    fun imageUrl(item: Item): String = "${base()}${item.image_url}"
    fun imageUrl(path: String): String = "${base()}$path"
}
