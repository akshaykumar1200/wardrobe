package com.wardrobe.ootd

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class SuggestState(
    val suggestions: List<Suggestion>? = null,
    val guidance: String? = null,
    val index: Int = 0,
    val error: String? = null,
    val unauthorized: Boolean = false,
    val loading: Boolean = false,
) {
    val onlyOne: Boolean get() = suggestions?.size == 1
}

class SuggestViewModel(private val api: Api) : ViewModel() {
    var state by mutableStateOf(SuggestState())
        private set

    fun start() = refresh()

    fun refresh() {
        if (state.loading) return
        state = state.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { api.suggestions() }
                state = state.copy(
                    suggestions = result.suggestions,
                    guidance = result.guidance,
                    index = 0,
                    error = null,
                )
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not load recommendations")
            } finally {
                state = state.copy(loading = false)
            }
        }
    }

    fun next() {
        val count = state.suggestions?.size ?: return
        if (count > 1) state = state.copy(index = (state.index + 1) % count)
    }

    fun consumeUnauthorized() { state = state.copy(unauthorized = false) }
}

class SuggestViewModelFactory(private val api: Api) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(SuggestViewModel::class.java)) return SuggestViewModel(api) as T
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
