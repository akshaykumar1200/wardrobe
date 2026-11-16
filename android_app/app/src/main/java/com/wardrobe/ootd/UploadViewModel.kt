package com.wardrobe.ootd

import android.content.ContentResolver
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

sealed class UploadState {
    data object Idle : UploadState()
    data class Uploading(val message: String, val seconds: Int) : UploadState()
    data class Review(val uploadId: Int, val candidates: List<UploadCandidate>, val notice: String?) : UploadState()
    data class Saving(val remaining: Int) : UploadState()
    data class Empty(val notice: String?) : UploadState()
    data class Failed(val message: String) : UploadState()
}

class UploadViewModel(private val api: Api) : ViewModel() {
    var state by mutableStateOf<UploadState>(UploadState.Idle)
        private set

    fun startUpload(uri: Uri, resolver: ContentResolver) {
        if (state is UploadState.Uploading || state is UploadState.Saving) return
        state = UploadState.Uploading("Preparing your photo...", 0)
        viewModelScope.launch {
            // withContext, not async: a failing async cancels this coroutine before
            // anything awaits it, so the catch below never ran and any upload error
            // killed the whole app instead of showing a message.
            val ticker = launch {
                var seconds = 0
                while (true) {
                    delay(1000)
                    seconds++
                    val message = when {
                        seconds < 5 -> "Uploading your photo..."
                        seconds < 20 -> "Finding your clothes..."
                        seconds < 40 -> "Separating each piece..."
                        else -> "Still working on your photo..."
                    }
                    state = UploadState.Uploading(message, seconds)
                }
            }
            try {
                val result = withContext(Dispatchers.IO) { api.upload(uri, resolver) }
                state = if (result.candidates.isEmpty()) {
                    UploadState.Empty(result.notice ?: "No clothes were found in this photo. Try another image.")
                } else {
                    UploadState.Review(result.upload_id, result.candidates, result.notice)
                }
            } catch (e: Exception) {
                state = UploadState.Failed(e.message ?: "Photo upload failed")
            } finally {
                ticker.cancel()
            }
        }
    }

    fun editCandidate(index: Int, candidate: UploadCandidate) {
        val current = state as? UploadState.Review ?: return
        state = current.copy(candidates = current.candidates.mapIndexed { i, old -> if (i == index) candidate else old })
    }

    fun removeCandidate(index: Int) {
        val current = state as? UploadState.Review ?: return
        val candidates = current.candidates.filterIndexed { i, _ -> i != index }
        state = if (candidates.isEmpty()) UploadState.Empty("No pieces selected. Choose another photo to add pieces.")
        else current.copy(candidates = candidates)
    }

    suspend fun save(onSaved: (Item) -> Unit) {
        val review = state as? UploadState.Review ?: return
        state = UploadState.Saving(review.candidates.size)
        try {
            review.candidates.forEachIndexed { index, candidate ->
                val saved = withContext(Dispatchers.IO) { api.saveCandidate(candidate, review.uploadId) }
                onSaved(saved)
                state = UploadState.Saving(review.candidates.size - index - 1)
            }
            state = UploadState.Idle
        } catch (e: Exception) {
            state = UploadState.Failed(e.message ?: "Could not save your pieces")
        }
    }

    fun dismiss() { state = UploadState.Idle }
    fun retry() { state = UploadState.Idle }
    fun error(message: String) { state = UploadState.Failed(message) }
}

class UploadViewModelFactory(private val api: Api) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(UploadViewModel::class.java)) return UploadViewModel(api) as T
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
