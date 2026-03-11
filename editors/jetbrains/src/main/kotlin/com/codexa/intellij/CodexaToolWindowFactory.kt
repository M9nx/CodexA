package com.codexa.intellij

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import javax.swing.*
import java.awt.BorderLayout
import java.net.HttpURLConnection
import java.net.URI

/**
 * CodexA tool window — provides semantic search within JetBrains IDEs.
 *
 * Communicates with the CodexA bridge server at http://localhost:24842.
 */
class CodexaToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = JPanel(BorderLayout())
        val searchField = JTextField()
        val resultArea = JTextArea()
        resultArea.isEditable = false

        searchField.addActionListener {
            val query = searchField.text.trim()
            if (query.isNotEmpty()) {
                resultArea.text = "Searching..."
                Thread {
                    val result = bridgeSearch(query)
                    SwingUtilities.invokeLater { resultArea.text = result }
                }.start()
            }
        }

        panel.add(searchField, BorderLayout.NORTH)
        panel.add(JScrollPane(resultArea), BorderLayout.CENTER)

        val content = ContentFactory.getInstance().createContent(panel, "Search", false)
        toolWindow.contentManager.addContent(content)
    }

    private fun bridgeSearch(query: String): String {
        return try {
            val url = URI("http://localhost:24842/request").toURL()
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            val body = """{"kind":"semantic_search","params":{"query":"$query","top_k":10}}"""
            conn.outputStream.use { it.write(body.toByteArray()) }
            conn.inputStream.bufferedReader().readText()
        } catch (e: Exception) {
            "Error: ${e.message}\n\nMake sure 'codexa serve' is running."
        }
    }
}
